"""failfirst plugin for Hermes Agent: /failfirst command plus a criteria-protection hook."""
from __future__ import annotations

import logging
import os
import shlex
from typing import Any, Dict, List, Optional

from . import _guard, _runner, _store

USAGE = """failfirst: fail-first acceptance gates for /goal
  /failfirst baseline [criteria]  run criteria on the UNFIXED code, then print a
                                  `/goal gate add ...` line for you to paste
  /failfirst status               run the gate now and report
  /failfirst release              drop this session's criteria protection
  /failfirst help                 this text"""

EXPLAIN = ("Baseline recorded: every criterion fails on the unfixed code.\n"
           "Next: run /goal <task>, then paste the line below to pin it as the goal's gate "
           "(Hermes accepts gates only once a goal exists; only you can add or change them). "
           "Until the gate is in place, a turn that edits code still cannot end while the "
           "criteria are red.")


def _split(raw: str) -> List[str]:
    try:
        return shlex.split(raw or "")
    except ValueError:
        return (raw or "").split()


def _resolve_criteria(args: List[str], cwd: str) -> str:
    if args:
        path = os.path.expanduser(args[0])
        return os.path.abspath(path if os.path.isabs(path) else os.path.join(cwd, path))
    return _runner.default_criteria(cwd) or ""


def _refusal(report: dict, detail: str) -> str:
    bad = _runner.bad_criteria(report)
    if bad:
        return ("Baseline refused, no gate created. These criteria do not fail on the "
                "unfixed code (vacuous criteria prove nothing):\n" + "\n".join(bad)
                + "\nFix the criteria and run /failfirst baseline again.")
    hint = ""
    if "FF_E_LOCK_EXISTS" in detail or "already exists" in detail:
        hint = ("\nA lockfile from an earlier baseline is in the way. If it belongs to a finished "
                "task, delete it yourself and run /failfirst baseline again on the unfixed code.")
    return f"Baseline failed, no gate created:\n{detail[:800]}{hint}"


def _baseline(args: List[str], session_id: str) -> str:
    if not session_id:
        return ("This chat has no session yet, so there is nothing to protect. Send one message "
                "first, then run /failfirst baseline again.")
    cli = _runner.find_failfirst()
    if cli is None:
        return "failfirst is not installed. Run: pip install failfirst"
    cwd = _runner.session_cwd()
    criteria = _resolve_criteria(args, cwd)
    if not criteria or not os.path.isfile(criteria):
        return "No criteria file found. Pass a path or create failfirst.json/.yaml/.yml."
    lock = os.path.join(os.path.dirname(criteria), _runner.LOCK_NAME)
    existed = os.path.exists(lock)
    code, report, detail = _runner.run_baseline(cli, criteria)
    if code != 0 or not os.path.isfile(lock):
        if not existed and os.path.isfile(lock):
            os.remove(lock)  # unclean baseline: let the user fix criteria and retry
        return _refusal(report, detail)
    sha = _runner.sha256_file(lock)
    _store.put(session_id, {"criteria": criteria, "lock": lock, "cwd": cwd, "sha": sha})
    gate = _runner.gate_command(cli, criteria, lock, sha)
    return f"{EXPLAIN}\n/goal gate add {gate}"


def _status(session_id: str) -> str:
    rec = _store.get(session_id)
    cli = _runner.find_failfirst()
    if rec is None or cli is None:
        return "No failfirst protection for this session. Run /failfirst baseline first."
    gate = _runner.gate_command(cli, rec["criteria"], rec["lock"], rec["sha"])
    code, tail = _runner.run_gate(gate, rec["cwd"])
    verdict = {0: "PASS", 3: "awaiting human review (judgment criteria)"}.get(code, "FAIL")
    return f"gate {verdict} (exit {code})\n{tail}"


def _pre_verify(session_id: str = "", **kwargs: Any) -> Optional[Dict[str, str]]:
    """Keep a turn that edited code going while this session's criteria are still red."""
    try:
        rec = _store.get(session_id, kwargs.get("conversation_id"))
        cli = _runner.find_failfirst()
        if rec is None or cli is None:
            return None
        gate = _runner.gate_command(cli, rec["criteria"], rec["lock"], rec["sha"])
        code, tail = _runner.run_gate(gate, rec["cwd"])
    except Exception:  # noqa: BLE001 - never wedge the turn; the goal gate still decides
        logging.getLogger(__name__).warning("failfirst pre_verify error", exc_info=True)
        return None
    if code in (0, 3):  # proven, or waiting for a human on judgment criteria
        return None
    return {"action": "continue", "message": (
        f"failfirst: the acceptance criteria are still not proven (exit {code}):\n{tail}\n"
        "Keep working on the code until they pass. Do not edit the criteria or the lockfile.")}


def _release(session_id: str) -> str:
    if _store.drop(session_id):
        return "failfirst protection released for this session."
    return "No failfirst protection was active for this session."


def _handler(raw_args: str = "", session_id: str = "", **_: Any) -> str:
    args = _split(raw_args)
    sub = args[0].lower() if args else "help"
    if sub == "baseline":
        return _baseline(args[1:], session_id)
    if sub == "status":
        return _status(session_id)
    if sub == "release":
        return _release(session_id)
    return USAGE


def register(ctx: Any) -> None:
    _store.load()
    ctx.register_command("failfirst", handler=_handler,
                         description="Fail-first acceptance gates for /goal",
                         args_hint="baseline [criteria] | status | release | help")
    ctx.register_hook("pre_tool_call", _guard.pre_tool_call)
    ctx.register_hook("pre_verify", _pre_verify)
