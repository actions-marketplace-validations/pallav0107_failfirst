#!/usr/bin/env python3
"""failfirst adapter for Grok Build (xAI's `grok` CLI): hooks, a baseline recorder and a runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

LOCK_NAME = ".failfirst.lock.json"
DEFAULT_CRITERIA = ("failfirst.json", "failfirst.yaml", "failfirst.yml")
DENY_MESSAGE = ("failfirst: this workspace's criteria file and lockfile are protected. "
                "Fix the code so the criteria pass; do not edit the criteria, the lockfile "
                "or re-run the baseline. A human can run `failfirst_grok.py release` if the "
                "criteria are genuinely wrong.")
_BASELINE = re.compile(r"(?<![\w.-])failfirst\s+(?:-\S+\s+)*baseline\b"
                       r"|failfirst_grok\S*\s+(?:-\S+\s+)*(?:baseline|release)\b")
_WRITE_WORDS = re.compile(
    r"(?<![\w-])(?:rm|mv|cp|tee|truncate|chmod|chown|shred|unlink|install|ln|rsync)(?![\w-])"
    r"|sed\s+(?:-\S+\s+)*-\S*i|perl\s+(?:-\S+\s+)*-\S*i"
    r"|git\s+(?:checkout|restore|rm|stash|reset|clean)\b|\bof=")
_SCRIPT_WRITE = re.compile(
    r"(?:python\S*\s+(?:-c|-\s*<<)|perl\s+(?:-\S+\s+)*-e|node\s+-e|ruby\s+-e)[\s\S]*?"
    r"(?:write|unlink|remove|rename|replace|truncate|shutil|open\([^)]*['\"][wax+])")
# grok 1.0.92 exposes write and search_replace; the rest are names its binary carries that a
# later version (or a subagent) might expose, denied the same way when they target a protected file.
WRITE_TOOLS = ("write", "search_replace", "write_file", "edit_file", "edit", "multi_edit",
               "apply_patch", "delete_file")
PATH_KEYS = ("file_path", "path", "filepath", "target_file")


# ---------------------------------------------------------------- paths and state

def grok_home() -> str:
    return os.path.expanduser(os.environ.get("GROK_HOME") or "~/.grok")


def state_dir() -> str:
    path = os.path.join(grok_home(), "failfirst")
    os.makedirs(path, exist_ok=True)
    return path


def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _save_json(path: str, data: Any) -> None:
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def records() -> Dict[str, Dict[str, str]]:
    data = _load_json(os.path.join(state_dir(), "workspaces.json"), {})
    return data if isinstance(data, dict) else {}


def save_records(recs: Dict[str, Dict[str, str]]) -> None:
    _save_json(os.path.join(state_dir(), "workspaces.json"), recs)


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def find_record(workspace_root: Optional[str], cwd: Optional[str]) -> Optional[Dict[str, str]]:
    """Record whose root equals the workspace root, else the deepest root containing cwd."""
    recs = records()
    if workspace_root and os.path.realpath(workspace_root) in recs:
        return recs[os.path.realpath(workspace_root)]
    if not cwd:
        return None
    real = os.path.realpath(cwd)
    best: Optional[Dict[str, str]] = None
    for root, rec in recs.items():
        if _within(real, root) and (best is None or len(root) > len(best["root"])):
            best = rec
    return best


# ---------------------------------------------------------------- failfirst invocation

def failfirst_cmd() -> Optional[List[str]]:
    exe = shutil.which("failfirst")
    if exe:
        return [exe]
    try:
        import importlib.util
        if importlib.util.find_spec("failfirst") is not None:
            return [sys.executable, "-m", "failfirst"]
    except (ImportError, ValueError):
        pass
    return None


def run_failfirst(args: List[str], cwd: str) -> Tuple[int, str]:
    cmd = failfirst_cmd()
    if cmd is None:
        return 2, "failfirst is not installed (pip install failfirst)"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(cmd + args, cwd=cwd, env=env, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr)


def tail(text: str, lines: int = 25) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def gate(rec: Dict[str, str]) -> Tuple[int, str]:
    """Run the gate for a record: (exit code, detail). 0 proven, 3 awaits human, else red."""
    lock = rec["lock"]
    try:
        current = sha256_file(lock)
    except OSError:
        return 1, "lockfile is missing: %s" % lock
    if current != rec["sha"]:
        return 1, "lockfile %s no longer matches the baseline recorded for this workspace" % lock
    code, out = run_failfirst(["verify", rec["criteria"], "--lock", lock, "--json"],
                              os.path.dirname(rec["criteria"]))
    return code, explain(out, rec["criteria"])


def _check_text(check: Any) -> str:
    """One line saying what a criterion's check runs or looks for."""
    if not isinstance(check, dict):
        return ""
    if "cmd" in check or "argv" in check:
        return "runs: %s" % (check.get("cmd") or " ".join(map(str, check.get("argv") or [])))
    if "path" in check:
        return "file %s must contain %r" % (check.get("path"), check.get("expect_contains"))
    if "url" in check:
        return "requests %s" % check.get("url")
    return ""


def _criteria_checks(criteria: str) -> Dict[str, Any]:
    """id -> check from the criteria file (JSON only; YAML needs PyYAML, which may be absent)."""
    try:
        with open(criteria, encoding="utf-8") as fh:
            text = fh.read()
        try:
            data = json.loads(text)
        except ValueError:
            import yaml  # type: ignore[import-not-found]
            data = yaml.safe_load(text)
        return {str(c.get("id")): c.get("check") for c in data.get("criteria", [])}
    except Exception:  # noqa: BLE001 - details are a convenience
        return {}


def explain(out: str, criteria: str) -> str:
    """Turn a verify --json report into lines naming each unproven criterion and its check."""
    report = _parse_json(out)
    if not isinstance(report, dict) or "criteria" not in report:
        return tail(out)
    checks = _criteria_checks(criteria)
    summ = ", ".join("%s %s" % (n, k) for k, n in sorted((report.get("summary") or {}).items()))
    lines = ["failfirst verify: %s (%s)" % (report.get("status"), summ)]
    for c in report["criteria"]:
        if c.get("verdict") == "proven":
            continue
        what = _check_text(checks.get(str(c.get("id"))))
        lines.append("- %s [%s]: %s%s%s" % (
            c.get("id"), c.get("verdict"), c.get("statement") or "", " | " if c.get("statement") else "",
            "%s; now: %s" % (what, c.get("reason")) if what else "now: %s" % c.get("reason")))
    return "\n".join(lines)


def verdict_word(code: int) -> str:
    return {0: "PROVEN", 3: "AWAITING HUMAN (judgment criteria)"}.get(code, "NOT PROVEN")


# ---------------------------------------------------------------- baseline / release / status

def find_criteria(arg: Optional[str]) -> Optional[str]:
    if arg:
        return os.path.abspath(arg)
    for name in DEFAULT_CRITERIA:
        if os.path.isfile(name):
            return os.path.abspath(name)
    return None


def _parse_json(text: str) -> Any:
    start = text.find("{")
    try:
        return json.loads(text[start:]) if start >= 0 else None
    except ValueError:
        return None


def _unclean_ids(data: Any) -> List[str]:
    found: List[str] = []
    items = data.get("criteria", []) if isinstance(data, dict) else []
    for item in items:
        if isinstance(item, dict) and (item.get("vacuous") or item.get("errored")
                                       or item.get("status") == "errored"):
            kind = "vacuous" if item.get("vacuous") else "errored"
            found.append("%s (%s)" % (item.get("id", "?"), kind))
    return found


def _refuse_baseline(out: str, lock: str, existed: bool) -> int:
    if not existed and os.path.exists(lock):
        os.remove(lock)
    names = _unclean_ids(_parse_json(out)) or ["see output below"]
    print("failfirst_grok: baseline refused, vacuous or errored criteria:")
    for name in names:
        print("  - " + name)
    print("A criterion that already passes on the unfixed code proves nothing. "
          "Fix the criteria, then re-run baseline.\n" + tail(out))
    return 1


def cmd_baseline(args: argparse.Namespace) -> int:
    criteria = find_criteria(args.criteria)
    if criteria is None or not os.path.isfile(criteria):
        print("failfirst_grok: no criteria file (looked for %s)" % ", ".join(DEFAULT_CRITERIA))
        return 2
    cdir = os.path.dirname(criteria)
    lock = os.path.join(cdir, LOCK_NAME)
    existed = os.path.exists(lock)
    code, out = run_failfirst(["baseline", criteria, "--json"], cdir)
    if code == 1:
        return _refuse_baseline(out, lock, existed)
    if code != 0:
        print("failfirst_grok: baseline failed (exit %d):\n%s" % (code, tail(out)))
        return 2
    root = os.path.realpath(os.getcwd())
    recs = records()
    recs[root] = {"root": root, "criteria": criteria, "lock": lock, "sha": sha256_file(lock)}
    save_records(recs)
    print("Baselined %s: every criterion fails on the unfixed code.\nLock: %s\n"
          "Next: python3 failfirst_grok.py run -- \"<task>\"  (or run `grok` with the hooks "
          "from install-hooks)." % (criteria, lock))
    return 0


def cmd_release(_: argparse.Namespace) -> int:
    recs = records()
    root = os.path.realpath(os.getcwd())
    if recs.pop(root, None) is None:
        print("failfirst_grok: no record for %s" % root)
        return 0
    save_records(recs)
    print("Released %s" % root)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    rec = find_record(None, os.getcwd())
    if rec is None:
        print("failfirst_grok: no baseline recorded for %s" % os.getcwd())
        return 2
    code, out = gate(rec)
    print("%s (exit %d)\n%s" % (verdict_word(code), code, out))
    return code


# ---------------------------------------------------------------- hooks

def read_payload() -> Dict[str, Any]:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _norm(path: str, cwd: str) -> str:
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.realpath(os.path.normpath(path))


def _names(rec: Dict[str, str], cwd: str) -> List[str]:
    out: List[str] = []
    for key in ("criteria", "lock"):
        full = rec[key]
        out += [full, os.path.basename(full)]
        for base in (cwd, rec["root"]):
            try:
                out.append(os.path.relpath(full, base))
            except ValueError:
                pass
    return sorted(set(out), key=len, reverse=True)


def _mentions(text: str, names: List[str]) -> List[str]:
    return [n for n in names
            if re.search(r"(?<![\w.-])" + re.escape(n) + r"(?![\w-])", text)]


def _redirects_onto(command: str, names: List[str]) -> bool:
    for name in names:
        base = re.escape(os.path.basename(name))
        if re.search(r">>?\s*['\"]?(?:[^\s'\";&|]*/)?" + base + r"(?![\w-])", command):
            return True
    return False


def terminal_blocked(command: str, rec: Dict[str, str], cwd: str) -> bool:
    if _BASELINE.search(command):
        return True
    hits = _mentions(command, _names(rec, cwd))
    if not hits:
        return False
    return (_redirects_onto(command, hits) or bool(_WRITE_WORDS.search(command))
            or bool(_SCRIPT_WRITE.search(command)))


def path_blocked(tool_input: Dict[str, Any], rec: Dict[str, str], cwd: str) -> bool:
    targets = [_norm(rec["criteria"], cwd), _norm(rec["lock"], cwd)]
    for key in PATH_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str) and val and _norm(val, cwd) in targets:
            return True
    return False


def should_deny(tool: str, tool_input: Any, rec: Dict[str, str], cwd: str) -> bool:
    if not isinstance(tool_input, dict):
        return False
    if tool in WRITE_TOOLS:
        return path_blocked(tool_input, rec, cwd)
    if tool == "run_terminal_command":
        cmd = tool_input.get("command")
        return isinstance(cmd, str) and terminal_blocked(cmd, rec, cwd)
    return False


def hook_pre_tool_use() -> int:
    try:
        p = read_payload()
        cwd = p.get("cwd") or os.getcwd()
        rec = find_record(p.get("workspaceRoot"), cwd)
        if rec is None:
            return 0
        if should_deny(str(p.get("toolName", "")), p.get("toolInput"), rec, cwd):
            print(json.dumps({"decision": "deny", "reason": DENY_MESSAGE}))
            return 2
    except Exception:  # noqa: BLE001 - fail open; `run`'s final verify is the real guard
        return 0
    return 0


def _counts_path() -> str:
    return os.path.join(state_dir(), "stop_counts.json")


def _get_count(sid: str) -> int:
    value = _load_json(_counts_path(), {}).get(sid, 0)
    return value if isinstance(value, int) else 0


def _set_count(sid: str, n: int) -> None:
    counts = _load_json(_counts_path(), {})
    if n:
        counts[sid] = n
    else:
        counts.pop(sid, None)
    _save_json(_counts_path(), counts)


def _max_blocks() -> int:
    try:
        return int(os.environ.get("FAILFIRST_GROK_MAX_STOP_BLOCKS", "5"))
    except ValueError:
        return 5


def hook_stop() -> int:
    try:
        p = read_payload()
        rec = find_record(p.get("workspaceRoot"), p.get("cwd") or os.getcwd())
        if rec is None or p.get("reason", "end_turn") != "end_turn":
            return 0
        sid = str(p.get("sessionId") or p.get("session_id") or "cwd:" + rec["root"])
        code, out = gate(rec)
        if code in (0, 3):
            _set_count(sid, 0)
            return 0
        n = _get_count(sid)
        if n >= _max_blocks():
            return 0
        _set_count(sid, n + 1)
        reason = ("failfirst: criteria not proven (exit %d):\n%s\nKeep fixing the code; "
                  "do not edit the criteria or lockfile." % (code, out))
        print(json.dumps({"decision": "block", "reason": reason}))
        return 2
    except Exception:  # noqa: BLE001 - fail open
        return 0


# ---------------------------------------------------------------- run / install-hooks

def grok_bin() -> Optional[str]:
    return os.environ.get("FAILFIRST_GROK_BIN") or shutil.which("grok")


def _grok_round(grok: str, prompt: str, model: Optional[str], cont: bool, cwd: str) -> int:
    # --single=<prompt>: a task starting with "-" would otherwise be parsed as a grok flag.
    cmd = [grok, "--single=" + prompt, "--no-auto-update", "--always-approve",
           "--output-format", "plain"]
    if cont:
        cmd.append("-c")
    if model:
        cmd += ["-m", model]
    rc = subprocess.run(cmd, cwd=cwd).returncode
    if rc != 0:
        print("failfirst_grok: grok exited %d this round" % rc, file=sys.stderr)
    return rc


def cmd_run(args: argparse.Namespace) -> int:
    task = " ".join(a for a in args.task if a != "--").strip()
    cwd = os.getcwd()
    rec = find_record(None, cwd)
    grok = grok_bin()
    if rec is None or not task or not grok:
        print("failfirst_grok: run needs a baseline for this directory (`baseline` first), "
              "a task (`run -- \"<task>\"`) and grok on PATH or FAILFIRST_GROK_BIN.")
        return 2
    prompt, code, out, rnd = task, 1, "", 0
    for rnd in range(1, max(1, args.max_rounds) + 1):
        _grok_round(grok, prompt, args.model, rnd > 1, cwd)
        code, out = gate(rec)
        if code in (0, 3):
            break
        prompt = ("%s\n\nfailfirst says the acceptance criteria are still not proven:\n%s\n"
                  "Fix the code (not the criteria)." % (task, out))
    print("failfirst_grok: %s after %d round(s) (exit %d)" % (verdict_word(code), rnd, code))
    if code not in (0, 3):
        print(out)
    return code if code in (0, 3) else 1


def cmd_install_hooks(_: argparse.Namespace) -> int:
    me = os.path.abspath(__file__)
    base = "%s %s" % (shlex.quote(os.path.abspath(sys.executable)), shlex.quote(me))

    def entry(sub: str, timeout: int) -> List[Dict[str, Any]]:
        return [{"hooks": [{"type": "command", "command": "%s hook %s" % (base, sub),
                            "timeout": timeout}]}]

    hooks = {"hooks": {"PreToolUse": entry("pre-tool-use", 15), "Stop": entry("stop", 600)}}
    path = os.path.join(grok_home(), "hooks", "failfirst.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _save_json(path, hooks)
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="failfirst_grok.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("criteria", nargs="?")
    h = sub.add_parser("hook")
    h.add_argument("event", choices=["pre-tool-use", "stop"])
    r = sub.add_parser("run")
    r.add_argument("--max-rounds", type=int, default=3)
    r.add_argument("--model")
    r.add_argument("task", nargs=argparse.REMAINDER)
    for name in ("install-hooks", "status", "release"):
        sub.add_parser(name)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "hook":
        return hook_pre_tool_use() if args.event == "pre-tool-use" else hook_stop()
    table = {"baseline": cmd_baseline, "run": cmd_run, "install-hooks": cmd_install_hooks,
             "status": cmd_status, "release": cmd_release}
    return table[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
