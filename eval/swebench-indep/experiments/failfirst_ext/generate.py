"""Generate K=3 single-shot acceptance checks per instance with the registered check-writer.

Check-writer: Qwen `qwen3.7-plus` through the PREPAID token-plan endpoint of Alibaba Model
Studio (OpenAI-compatible). The credential is read from the process environment, or from
the dotenv file named by the FFX_ENV_FILE environment variable (no default path). It is
accepted only if it has the prepaid token-plan shape, is sent only to TOKEN_PLAN_HOST, and
is never printed, logged or written anywhere. A refused credential STOPS the run; there is
no fallback to any other credential, endpoint or model.

Every API reply is one logged attempt (attempt 0, then at most two regenerations for an
empty or unparseable reply). Each row carries the sha256 of the script extracted from that
reply; the check file is the first usable reply. An interrupted run resumes a slot from its
logged attempts and never re-numbers or repeats an attempt.

Input to the model: repo name, version and problem_statement only (prompt.txt).

  python generate.py --pilot ID [ID ...] --run-dir DIR       # pilot ids; before the freeze only
                                                             # an absent freeze is tolerated
  python generate.py --lock sample.lock.json --run-dir DIR   # sampled ids: frozen prereg AND the
                                                             # frozen lock, byte for byte

Outputs in DIR: checks/<instance>/check_<k>.py, generations.jsonl (one row per API call:
returned model string, usage, finish reason, hashes), run_manifest.json.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

TOKEN_PLAN_HOST = "token-plan.ap-southeast-1.maas.aliyuncs.com"
BASE_URL = f"https://{TOKEN_PLAN_HOST}/compatible-mode/v1"
MODEL = "qwen3.7-plus"
PARAMS = {"temperature": 0.7, "top_p": 0.8, "max_tokens": 4096, "enable_thinking": False}
CHECK_SEEDS = (1, 2, 3)
MAX_REGENERATIONS = 2           # only for an empty or unparseable reply
#: Prepaid token-plan credentials have this prefix; a pay-as-you-go key does not.
PREPAID_PREFIX = "sk-" + "sp-"
#: Variable names searched, in order. A metered pay-as-you-go credential is never among them.
KEY_NAMES = ("QWEN_CLOUD_API_KEY", "DASHSCOPE_API_KEY", "QWEN_API_KEY", "qwen")
ENV_FILE_VAR = "FFX_ENV_FILE"
#: Stub written when a slot has no usable reply after the regenerations: exits 127, which
#: the registered rule classifies as ERROR, so the slot is counted and is never green.
STUB = "import sys\nsys.exit(127)  # no usable reply from the check-writer\n"


class Refused(SystemExit):
    """The endpoint refused the prepaid credential: stop, never switch credentials."""


def regen_seed(k: int, attempt: int) -> int:
    return CHECK_SEEDS[k - 1] if attempt == 0 else 100 * k + attempt


def env_file_path() -> Path | None:
    value = (os.environ.get(ENV_FILE_VAR) or "").strip()
    return Path(value) if value else None


def read_dotenv(path: Path) -> dict[str, str]:
    """KEY=VALUE, optional `export`, optional quotes, # comments. No shell evaluation."""
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.replace("export", "", 1).strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            out[name] = value
    return out


def prepaid_key(env_file: Path | None) -> tuple[str | None, str]:
    """(key, source-name). Only a prepaid token-plan credential is ever returned."""
    file_vals = read_dotenv(env_file) if env_file else {}
    for name in KEY_NAMES:
        value = (os.environ.get(name) or file_vals.get(name) or "").strip()
        if value and value.startswith(PREPAID_PREFIX):
            return value, name
    return None, "no prepaid token-plan credential found under " + ", ".join(KEY_NAMES)


def egress_ok(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() == TOKEN_PLAN_HOST


def render_prompt(template: str, inst: dict) -> str:
    out = template.replace("{{REPO}}", str(inst["repo"]))
    out = out.replace("{{VERSION}}", str(inst["version"]))
    return out.replace("{{PROBLEM_STATEMENT}}", str(inst["problem_statement"]).strip())


_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.S)


def extract_script(reply: str) -> str | None:
    """First fenced code block, else the whole reply if it parses. None if unusable."""
    m = _FENCE.search(reply or "")
    code = m.group(1) if m else (reply or "")
    code = code.strip("\n")
    if not code.strip():
        return None
    try:
        ast.parse(code)
    except SyntaxError:
        return None
    return code + "\n"


def call_model(key: str, prompt: str, seed: int, *, timeout_s: int = 300) -> dict:
    """One chat completion. Returns a record WITHOUT the credential or the prompt text."""
    url = f"{BASE_URL}/chat/completions"
    if not egress_ok(url):
        raise Refused(f"BLOCKED: refusing to send the credential to {urlparse(url).hostname}")
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "seed": seed, "stream": False, **PARAMS}).encode("utf-8")
    delay = 5.0
    transport_retries = 0
    for attempt in range(6):
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                payload = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            if exc.code in (401, 403):
                raise Refused(f"BLOCKED: the token-plan endpoint refused the prepaid credential "
                              f"(HTTP {exc.code}). Not switching credentials. {detail}")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                transport_retries += 1
                time.sleep(delay)
                delay *= 2
                continue
            return {"ok": False, "error": f"HTTP {exc.code}: {detail}", "transport_retries": transport_retries}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt < 5:
                transport_retries += 1
                time.sleep(delay)
                delay *= 2
                continue
            return {"ok": False, "error": type(exc).__name__, "transport_retries": transport_retries}
    choice = (payload.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content") or "")
    if "invalid access token" in text.lower() or text.startswith("[API Error:"):
        raise Refused("BLOCKED: the endpoint returned an auth error in the message body")
    usage = payload.get("usage") or {}
    return {"ok": True, "text": text, "returned_model": payload.get("model"),
            "finish_reason": choice.get("finish_reason"), "response_id": payload.get("id"),
            "transport_retries": transport_retries,
            "system_fingerprint": payload.get("system_fingerprint"),
            "usage": {"input": int(usage.get("prompt_tokens") or 0),
                      "output": int(usage.get("completion_tokens") or 0),
                      "total": int(usage.get("total_tokens") or 0)}}


def generate_slot(key: str, template: str, inst: dict, k: int, check_dir: Path,
                  log, caller=call_model, prior: list[dict] | None = None) -> dict:
    """Fill one check slot. `prior` = this slot's already-logged attempts (resume)."""
    prompt = render_prompt(template, inst)
    prompt_sha = C.sha256_bytes(prompt.encode("utf-8"))
    path = check_dir / inst["instance_id"] / f"check_{k}.py"
    prior = sorted(prior or [], key=lambda r: r["attempt"])
    script_sha = None
    for r in prior:                      # resume: a usable reply already logged is final
        if r.get("usable"):
            if not path.exists() or C.sha256_file(path) != r.get("script_sha256"):
                raise SystemExit(f"BLOCKED: {inst['instance_id']}#{k}: logged usable reply has no "
                                 f"matching check file; refusing to regenerate")
            script_sha = r["script_sha256"]
            break
    attempts = len(prior)
    while script_sha is None and attempts < MAX_REGENERATIONS + 1:
        attempt = attempts
        attempts += 1
        seed = regen_seed(k, attempt)
        rec = caller(key, prompt, seed)
        code = extract_script(rec.get("text", "")) if rec.get("ok") else None
        if code is not None:             # written BEFORE logging, so a resume can trust the log
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding="utf-8", newline="\n")
            script_sha = C.sha256_file(path)
        log({"instance_id": inst["instance_id"], "k": k, "attempt": attempt, "seed": seed,
             "ok": bool(rec.get("ok")), "usable": code is not None,
             "script_sha256": script_sha if code is not None else None,
             "returned_model": rec.get("returned_model"), "finish_reason": rec.get("finish_reason"),
             "response_id": rec.get("response_id"), "system_fingerprint": rec.get("system_fingerprint"),
             "transport_retries": rec.get("transport_retries"),
             "usage": rec.get("usage"), "error": rec.get("error"),
             "rendered_prompt_sha256": prompt_sha,
             "reply_sha256": C.sha256_bytes(rec.get("text", "").encode("utf-8")) if rec.get("ok") else None,
             "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    failed = script_sha is None
    if failed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(STUB, encoding="utf-8", newline="\n")
    return {"check_id": f"{inst['instance_id']}#{k}", "instance_id": inst["instance_id"], "k": k,
            "check_sha256": C.sha256_file(path), "generation_failed": failed, "attempts": attempts,
            "path": f"checks/{inst['instance_id']}/check_{k}.py"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pilot", nargs="+", metavar="ID")
    src.add_argument("--lock")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)

    # An existing freeze binds every mode; an absent one is tolerated only for pilot work.
    ok, msg = C.prereg_gate(C.HERE, require_frozen=not args.pilot)
    if not ok:
        print(msg + " -- refusing to generate")
        return 3
    pilot = set(C.read_lines(C.HERE / "pilot_ids.txt"))
    if args.pilot:
        ids = list(args.pilot)
        bad = [i for i in ids if i not in pilot]
        if bad:
            print(f"BLOCKED: --pilot accepts only the registered pilot ids; not pilot: {bad}")
            return 2
    else:
        ok, msg = C.lock_gate(C.HERE, args.lock)
        if not ok:
            print(msg)
            return 3
        lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
        ids = [i["instance_id"] for i in lock["instances"]]
        if set(ids) & pilot:
            print("BLOCKED: the lock contains pilot ids")
            return 2

    key, source = prepaid_key(env_file_path())
    if key is None:
        print("BLOCKED: " + source + ". The metered pay-as-you-go credential is never used.")
        return 2
    print(f"credential: prepaid token plan (from {source}); endpoint host {TOKEN_PLAN_HOST}; model {MODEL}")

    import fetch_patches as F
    ds = F.load_dataset()
    template = (C.HERE / "prompt.txt").read_text(encoding="utf-8")
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    gen_log = run_dir / "generations.jsonl"
    lk = threading.Lock()

    def log(row: dict) -> None:
        with lk, gen_log.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    done = {}
    man_path = run_dir / "run_manifest.json"
    if man_path.exists():
        for c in json.loads(man_path.read_text(encoding="utf-8")).get("checks", []):
            done[c["check_id"]] = c
    prior = {}
    if gen_log.exists():
        for ln in gen_log.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                prior.setdefault((r["instance_id"], r["k"]), []).append(r)
    slots = [(iid, k) for iid in ids for k in range(1, C.K_CHECKS + 1) if f"{iid}#{k}" not in done]
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(generate_slot, key, template, ds[iid], k, run_dir / "checks", log,
                              call_model, prior.get((iid, k)))
                    for iid, k in slots]
            for f in futs:
                c = f.result()
                done[c["check_id"]] = c
                print(f"  {c['check_id']}: {'STUB (no usable reply)' if c['generation_failed'] else 'ok'}"
                      f" attempts={c['attempts']}", flush=True)
    except Refused as exc:
        print(str(exc))
        return 2
    finally:
        del key
    rows = [json.loads(ln) for ln in gen_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    models = sorted({r["returned_model"] for r in rows if r.get("ok") and r.get("returned_model")})
    manifest = {
        "task_id": C.TASK_ID, "mode": "pilot" if args.pilot else "sampled",
        "endpoint_host": TOKEN_PLAN_HOST, "model_requested": MODEL,
        "params": dict(PARAMS, check_seeds=list(CHECK_SEEDS), max_regenerations=MAX_REGENERATIONS),
        "prompt_sha256": C.sha256_file(C.HERE / "prompt.txt"),
        "returned_models": models,
        "checks": [done[k] for k in sorted(done)],
    }
    man_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                        newline="\n")
    usage = [r.get("usage") or {} for r in rows]
    print(f"calls={len(rows)} returned_models={models} tokens in={sum(u.get('input', 0) for u in usage)} "
          f"out={sum(u.get('output', 0) for u in usage)}")
    if len(models) > 1:
        print("BLOCKED: more than one distinct returned model string")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
