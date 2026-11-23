#!/usr/bin/env python3
"""Deviation D1 supplementary runner (box side, standard library only).

Runs ONLY the 15 runs pre-listed in dev1_keys.json, once each (attempt 3), reusing the
frozen box_runner.py unchanged except for the in-container apply step:

  git apply; on failure  patch --batch --fuzz=5 -p1  (the official harness's final fallback)
  post-condition: every patch hunk OUTSIDE the pre-listed setup file must be present in the
  tree afterwards (the sub-patch without the setup file reverse-applies cleanly).

The run counts as applied only if the apply step exited 0 AND the post-condition held; the
check is then executed exactly as in the registered runner. Rows go to dev1_results.jsonl in
the bundle directory, never to results.jsonl.

  python3 dev1_runner.py --bundle DIR --keys dev1_keys.json
Refuses to run if results.jsonl differs from the hashed file, if the set of incomplete runs in
results.jsonl differs from the pre-listed keys, or if dev1_results.jsonl already has rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path

D1_ATTEMPT = 3
#: box/box_runner.py as listed in the frozen PREREG.sha256
FROZEN_BOX_RUNNER_SHA256 = "990f1e9297f65b362545e6aa0ffb81a1f7c1159c9d73f9049447daf54bcfb6fe"
STATE: dict = {}


def d1_script(nonce: str, timeout_s: int, setup_file: str) -> str:
    sf = shlex.quote(setup_file)
    hdr = shlex.quote("diff --git a/" + setup_file + " b/" + setup_file)
    lines = [
        "source /opt/miniconda3/bin/activate >/dev/null 2>&1",
        "conda activate testbed >/dev/null 2>&1",
        "cd /testbed",
        "step=git_apply",
        "git apply /ffx/patch.diff >/dev/null 2>/tmp/ffx_apply.err; s=$?",
        'if [ "$s" -ne 0 ]; then step=patch_fuzz5; '
        "patch --batch --fuzz=5 -p1 -i /ffx/patch.diff >/tmp/ffx_patch.log 2>&1; s=$?; fi",
        f"awk -v h={hdr} '/^diff --git /{{skip=($0==h)}} !skip' /ffx/patch.diff > /tmp/ffx_sub.diff",
        "git apply --check -R /tmp/ffx_sub.diff >/dev/null 2>&1; pc=$?",
        f"git diff --quiet HEAD -- {sf}; sfd=$?",
        f'echo; echo "FFX_{nonce}_STEP=$step S=$s POSTCOND=$pc SETUP_DIFFERS_FROM_HEAD=$sfd"',
        'if [ "$s" -eq 0 ] && [ "$pc" -eq 0 ]; then arc=0; else arc=1; fi',
        f'echo "FFX_{nonce}_APPLY=$arc"',
        'if [ "$arc" -ne 0 ]; then exit 0; fi',
        f"timeout -k 5 {int(timeout_s)} python /ffx/check.py",
        f'rc=$?; echo; echo "FFX_{nonce}_RC=$rc"',
    ]
    return "\n".join(lines) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--keys", required=True)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args(argv)
    bundle = Path(args.bundle).resolve()
    spec = json.loads(Path(args.keys).read_text(encoding="utf-8"))
    if sha256_file(bundle / "box_runner.py") != FROZEN_BOX_RUNNER_SHA256:
        print("REFUSED: bundle box_runner.py is not the frozen runner")
        return 2
    sys.path.insert(0, str(bundle))
    import box_runner as BR  # the frozen runner shipped in the bundle

    res = bundle / "results.jsonl"
    if sha256_file(res) != spec["results_jsonl_sha256"]:
        print("REFUSED: results.jsonl differs from the hashed registered results")
        return 2
    rows = [json.loads(ln) for ln in res.read_text(encoding="utf-8").splitlines() if ln.strip()]
    done = {(r["check_id"], r["target"]) for r in rows if BR.row_completed(r)}
    incomplete = {(r["check_id"], r["target"]) for r in rows} - done
    want = {(k["check_id"], k["target"]) for k in spec["keys"]}
    if incomplete != want or len(want) != 15:
        print(f"REFUSED: incomplete runs {len(incomplete)} differ from the pre-listed {len(want)}")
        return 2
    out = bundle / "dev1_results.jsonl"
    if out.exists() and out.read_text(encoding="utf-8").strip():
        print("REFUSED: dev1_results.jsonl already has rows (no reruns)")
        return 2
    tasks = {(t["check_id"], t["target"]): t
             for t in json.loads((bundle / "tasks.json").read_text(encoding="utf-8"))["tasks"]}

    orig_parse = BR.parse_markers

    def parse_and_record(stdout: str, nonce: str):
        for line in stdout.splitlines():
            if f"FFX_{nonce}_STEP=" in line:
                STATE["d1_markers"] = line.split(f"FFX_{nonce}_STEP=", 1)[1].strip()
        return orig_parse(stdout, nonce)

    BR.parse_markers = parse_and_record
    for k in sorted(spec["keys"], key=lambda x: (x["instance_id"], x["target"], x["check_id"])):
        t = tasks[(k["check_id"], k["target"])]
        STATE.clear()
        BR.container_script = lambda nonce, timeout_s, with_patch, _sf=k["setup_file"]: d1_script(nonce, timeout_s, _sf)
        r = BR.run_task(bundle, t, args.timeout, D1_ATTEMPT)
        if r["check_sha256"] != k["check_sha256"] or r["patch_sha256"] != k["patch_sha256"]:
            print(f"REFUSED: hash mismatch for {k['check_id']} {k['target']}")
            return 2
        r["deviation"] = "D1"
        r["setup_file"] = k["setup_file"]
        r["d1_markers"] = STATE.get("d1_markers")
        r["timeout_s"] = args.timeout
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
        print(f"{r['check_id']} {r['target']} a{D1_ATTEMPT} {r['status']} applied={r['applied']} "
              f"[{r['d1_markers']}]", flush=True)
    print("D1 RUNNER DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
