#!/usr/bin/env python3
"""Box-side executor: run each generated check on the unfixed tree (twice), on each
candidate patch and on the gold patch, inside the public SWE-bench instance image.

Standard library only (runs on the execution host's system python3). Every container is
started with a unique name by this process, with --network none and --pull never (images
must already be present), and is killed only by that exact name on an outer timeout.

Registered rerun rule: a row is COMPLETED when an exit code was read from the in-container
marker, docker exited 0, the outer watchdog did not fire and (for a patched tree) the patch
applied. Anything else is MISSING and is retried exactly once (attempt 2). Every attempt is
logged with its attempt number and the host load average. A completed task is never re-run,
so a restart resumes without silent reruns.

  python3 box_runner.py --bundle DIR [--workers 6] [--timeout 120]

DIR/tasks.json lists tasks; results append to DIR/results.jsonl.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

EXC_LINE = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning)|AssertionError)\b")


MAX_ATTEMPTS = 2


def loadavg() -> float | None:
    try:
        return float(Path("/proc/loadavg").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def row_completed(r: dict) -> bool:
    """Same rule as common.row_completed (this file must run without the rest of the package)."""
    if r.get("exit_code") is None or r.get("docker_rc") != 0 or r.get("outer_timeout"):
        return False
    if r.get("patch_sha256") is not None and r.get("applied") is not True:
        return False
    return True


def pending(tasks: list[dict], rows: list[dict], max_attempts: int = MAX_ATTEMPTS) -> list[tuple[dict, int]]:
    """(task, next attempt number) for every task without a completed row that still has an
    attempt left under the registered rule."""
    hist: dict = {}
    for r in rows:
        hist.setdefault((r["check_id"], r["target"]), []).append(r)
    out = []
    for t in tasks:
        rs = hist.get((t["check_id"], t["target"]), [])
        if any(r.get("status") == "completed" for r in rs):
            continue
        n = max([r.get("attempt", 1) for r in rs], default=0)
        if n < max_attempts:
            out.append((t, n + 1))
    return out


def strict_assertion(stderr: str) -> bool:
    """True only when the LAST traceback on stderr ends in AssertionError and passes through
    the check's own file. A printed message mentioning AssertionError, an assertion inside a
    library only, or an AssertionError followed by another exception does not count."""
    marker = "Traceback (most recent call last):"
    if marker not in stderr:
        return False
    last = stderr[stderr.rindex(marker):]
    lines = [ln for ln in last.splitlines() if ln.strip()]
    if not lines or not lines[-1].strip().startswith("AssertionError"):
        return False
    return any('File "/ffx/check.py"' in ln for ln in lines)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def container_script(nonce: str, timeout_s: int, with_patch: bool) -> str:
    """Shell run inside the container. Markers carry a per-run nonce so the check's own
    output can never be mistaken for them."""
    lines = [
        "source /opt/miniconda3/bin/activate >/dev/null 2>&1",
        "conda activate testbed >/dev/null 2>&1",
        "cd /testbed",
    ]
    if with_patch:
        lines += [
            "git apply /ffx/patch.diff >/dev/null 2>/tmp/ffx_apply.err; arc=$?",
            f'echo; echo "FFX_{nonce}_APPLY=$arc"',
            'if [ "$arc" -ne 0 ]; then exit 0; fi',
        ]
    lines += [
        f"timeout -k 5 {int(timeout_s)} python /ffx/check.py",
        f'rc=$?; echo; echo "FFX_{nonce}_RC=$rc"',
    ]
    return "\n".join(lines) + "\n"


def parse_markers(stdout: str, nonce: str) -> tuple[int | None, bool | None]:
    """(check exit code or None, patch applied or None when no patch)."""
    rc = applied = None
    for line in stdout.splitlines():
        m = re.search(rf"FFX_{nonce}_APPLY=(\d+)", line)
        if m:
            applied = m.group(1) == "0"
        m = re.search(rf"FFX_{nonce}_RC=(\d+)", line)
        if m:
            rc = int(m.group(1))
    return rc, applied


def exception_type(stderr: str) -> str | None:
    """Type of the last exception in a Python traceback on stderr, if any."""
    if "Traceback (most recent call last)" not in stderr:
        return None
    last = None
    for line in stderr.splitlines():
        m = EXC_LINE.match(line.strip())
        if m:
            last = m.group(1)
    return last


def docker_cmd(name: str, image: str, check: Path, patch: Path | None, script: str) -> list[str]:
    cmd = ["docker", "run", "--rm", "--name", name, "--network", "none", "--pull", "never",
           "--memory", "8g", "--cpus", "2",
           "-v", f"{check}:/ffx/check.py:ro"]
    if patch is not None:
        cmd += ["-v", f"{patch}:/ffx/patch.diff:ro"]
    cmd += ["--entrypoint", "/bin/bash", image, "-c", script]
    return cmd


def run_task(bundle: Path, t: dict, timeout_s: int, attempt: int = 1) -> dict:
    nonce = secrets.token_hex(6)
    name = f"ffx_{nonce}"
    check = (bundle / t["check"]).resolve()
    patch = (bundle / t["patch"]).resolve() if t.get("patch") else None
    script = container_script(nonce, timeout_s, patch is not None)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    load_start = loadavg()
    t0 = time.time()
    outer_timeout = False
    try:
        proc = subprocess.run(docker_cmd(name, t["image"], check, patch, script),
                              capture_output=True, text=True, errors="replace",
                              timeout=timeout_s + 180)
        stdout, stderr, docker_rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        outer_timeout = True
        subprocess.run(["docker", "kill", name], capture_output=True)   # only our own container
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        docker_rc = None
    rc, applied = parse_markers(stdout, nonce)
    if patch is None:
        applied = None
    row = {
        "check_id": t["check_id"], "instance_id": t["instance_id"], "target": t["target"],
        "attempt": attempt, "image": t["image"], "check_sha256": sha256_file(check),
        "patch_sha256": sha256_file(patch) if patch else None,
        "exit_code": rc, "timed_out": rc in (124, 137), "outer_timeout": outer_timeout,
        "applied": applied, "docker_rc": docker_rc,
        "assertion_error": strict_assertion(stderr), "exc_type": exception_type(stderr),
        "stderr_tail": stderr[-1500:], "stdout_tail": stdout[-500:],
        "duration_s": round(time.time() - t0, 2), "started_utc": started,
        "loadavg_1m_start": load_start, "loadavg_1m_end": loadavg(),
    }
    row["status"] = "completed" if row_completed(row) else "missing"
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args(argv)
    if args.workers > 6:
        print("refusing more than 6 workers (shared host)")
        return 2
    bundle = Path(args.bundle).resolve()
    tasks = json.loads((bundle / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    out = bundle / "results.jsonl"
    lock = threading.Lock()

    def read_rows():
        if not out.exists():
            return []
        return [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]

    for pass_no in range(1, MAX_ATTEMPTS + 1):
        todo = pending(tasks, read_rows(), MAX_ATTEMPTS)
        print(f"pass {pass_no}: {len(tasks)} tasks, {len(todo)} to run", flush=True)
        if not todo:
            break
        n = [0]

        def work(item, n=n, todo=todo):
            t, attempt = item
            r = run_task(bundle, t, args.timeout, attempt)
            with lock:
                with out.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(r, sort_keys=True) + "\n")
                n[0] += 1
                print(f"[{n[0]}/{len(todo)}] {r['check_id']} {r['target']} a{attempt} {r['status']} "
                      f"rc={r['exit_code']} applied={r['applied']} {r['duration_s']}s", flush=True)

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, todo))
    done = {(r["check_id"], r["target"]) for r in read_rows() if r.get("status") == "completed"}
    left = sum(1 for t in tasks if (t["check_id"], t["target"]) not in done)
    print(f"RUNNER DONE: {left} tasks still missing after the registered retry", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
