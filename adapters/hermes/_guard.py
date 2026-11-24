"""pre_tool_call guard: keep the criteria file and lockfile out of the agent's hands."""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

from . import _store

MESSAGE = ("failfirst: this session's criteria file and lockfile are protected. "
           "Fix the code so the criteria pass; do not edit the criteria or re-baseline. "
           "A human can run /failfirst release if the criteria are genuinely wrong.")
_V4A = re.compile(r"^\*\*\* (?:Update File|Add File|Delete File|Move to):\s*(.+?)\s*$", re.M)
_BASELINE = re.compile(r"(?<![\w.-])failfirst\s+(?:-\S+\s+)*baseline\b")
_WRITE_WORDS = re.compile(
    r"(?<![\w-])(?:rm|mv|cp|tee|truncate|chmod|chown|shred|unlink|install|ln|rsync)(?![\w-])"
    r"|sed\s+(?:-\S+\s+)*-\S*i|perl\s+(?:-\S+\s+)*-\S*i"
    r"|git\s+(?:checkout|restore|rm|stash|reset|clean)\b|\bof=")
_SCRIPT_WRITE = re.compile(
    r"(?:python\S*\s+-c|perl\s+(?:-\S+\s+)*-e|node\s+-e|ruby\s+-e)[\s\S]*?"
    r"(?:write|unlink|remove|rename|replace|truncate|shutil|open\([^)]*['\"][wax+])")
_CODE_WRITE = re.compile(
    r"write_file\s*\(|patch\s*\(|\.write(?:_text|_bytes)?\s*\(|\bunlink\s*\(|\bremove\s*\("
    r"|\brename\s*\(|\breplace\s*\(|\btruncate\s*\(|shutil\.|open\([^)]*['\"][wax+]"
    r"|terminal\s*\(")


def _norm(path: str, cwd: str) -> str:
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.realpath(os.path.normpath(path))


def _targets(rec: Dict[str, str]) -> List[str]:
    return [_norm(rec["criteria"], rec["cwd"]), _norm(rec["lock"], rec["cwd"])]


def _names(rec: Dict[str, str]) -> List[str]:
    out: List[str] = []
    for key in ("criteria", "lock"):
        full = rec[key]
        out += [full, os.path.basename(full)]
        try:
            out.append(os.path.relpath(full, rec["cwd"]))
        except ValueError:  # Windows: criteria and cwd on different drives
            pass
    return sorted(set(out), key=len, reverse=True)


def _mentions(text: str, rec: Dict[str, str]) -> List[str]:
    return [n for n in _names(rec)
            if re.search(r"(?<![\w.-])" + re.escape(n) + r"(?![\w-])", text)]


def _path_blocked(args: Dict[str, Any], rec: Dict[str, str]) -> bool:
    targets = _targets(rec)
    for key in ("path", "file_path", "filepath", "target", "new_path"):
        val = args.get(key)
        if isinstance(val, str) and val and _norm(val, rec["cwd"]) in targets:
            return True
    patch = args.get("patch")
    if isinstance(patch, str):
        return any(_norm(h, rec["cwd"]) in targets for h in _V4A.findall(patch))
    return False


def _redirects_onto(command: str, names: List[str]) -> bool:
    for name in names:
        base = re.escape(os.path.basename(name))
        if re.search(r">>?\s*['\"]?(?:[^\s'\";&|]*/)?" + base + r"(?![\w-])", command):
            return True
    return False


def _terminal_blocked(command: str, rec: Dict[str, str]) -> bool:
    if _BASELINE.search(command):
        return True
    hits = _mentions(command, rec)
    if not hits:
        return False
    return (_redirects_onto(command, hits) or bool(_WRITE_WORDS.search(command))
            or bool(_SCRIPT_WRITE.search(command)))


def check(tool_name: str, args: Any, rec: Dict[str, str]) -> bool:
    """True if this call must be blocked for a protected session."""
    if not isinstance(args, dict):
        return False
    if tool_name in ("write_file", "patch", "edit_file", "apply_patch"):
        return _path_blocked(args, rec)
    if tool_name == "terminal":
        cmd = args.get("command")
        return isinstance(cmd, str) and _terminal_blocked(cmd, rec)
    if tool_name == "execute_code":  # its nested tool calls hit this hook; raw file I/O does not
        code = args.get("code")
        return isinstance(code, str) and bool(_mentions(code, rec)) and bool(_CODE_WRITE.search(code))
    return False


def pre_tool_call(tool_name: str = "", args: Any = None, session_id: str = "",
                  conversation_id: str = "", **_: Any) -> Optional[Dict[str, str]]:
    try:
        rec = _store.get(session_id, conversation_id)
        if rec is None:
            return None
        _store.alias(conversation_id, rec)
        if check(tool_name, args, rec):
            return {"action": "block", "message": MESSAGE}
    except Exception:  # noqa: BLE001 - a guard bug must not wedge the agent; the gate still decides
        logging.getLogger(__name__).warning("failfirst guard error", exc_info=True)
    return None
