"""Per-session protection records, persisted under $HERMES_HOME/failfirst."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_SESSIONS: Dict[str, Dict[str, str]] = {}
REQUIRED = frozenset({"criteria", "lock", "cwd", "sha"})


def store_path() -> Path:
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / "failfirst" / "sessions.json"


def load() -> Dict[str, Dict[str, str]]:
    """Reload records from disk (missing or corrupt file means none)."""
    _SESSIONS.clear()
    try:
        data = json.loads(store_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _SESSIONS
    if isinstance(data, dict):
        for sid, rec in data.items():
            if isinstance(rec, dict) and REQUIRED <= rec.keys():
                _SESSIONS[str(sid)] = {k: str(v) for k, v in rec.items()}
    return _SESSIONS


def _save() -> None:
    path = store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(_SESSIONS, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # persistence is best effort; in-memory protection still holds


def put(session_id: str, record: Dict[str, str]) -> None:
    _SESSIONS[session_id] = record
    _save()


def alias(conversation_id: str, record: Dict[str, str]) -> None:
    """Also file ``record`` under the conversation's root id, which survives the session-id
    rotation that context compression performs (the command handler only sees the session id)."""
    if conversation_id and conversation_id not in _SESSIONS:
        _SESSIONS[conversation_id] = record
        _save()


def drop(session_id: str) -> bool:
    """Drop the session's record and every alias of it."""
    rec = _SESSIONS.get(session_id)
    if rec is None:
        return False
    for key in [k for k, v in _SESSIONS.items() if v == rec]:
        del _SESSIONS[key]
    _save()
    return True


def get(*session_ids: Optional[Any]) -> Optional[Dict[str, str]]:
    for sid in session_ids:
        if sid and str(sid) in _SESSIONS:
            return _SESSIONS[str(sid)]
    return None
