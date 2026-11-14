"""Criterion model: validation, normalisation and content hashing (see spec/SPEC.md)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

SPEC_VERSION = 1


class SpecError(Exception):
    """The criteria file (or a criterion in it) is malformed."""


_CHECK_FIELDS = {
    "command": {"type", "cmd", "argv", "cwd", "timeout", "expect_exit",
                "expect_contains", "expect_not_contains"},
    "file_contains": {"type", "path", "expect_contains", "expect_not_contains"},
    "http": {"type", "url", "method", "timeout", "expect_status",
             "expect_contains", "expect_not_contains"},
}


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _str_list(cid: str, key: str, v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return list(v)
    raise SpecError(f"criterion {cid!r}: {key} must be a string or list of strings")


def _int_field(cid: str, key: str, v: Any, default: int, minimum: int | None = None) -> int:
    if v is None:
        return default
    if not _is_int(v):
        raise SpecError(f"criterion {cid!r}: {key} must be an integer")
    if minimum is not None and v < minimum:
        raise SpecError(f"criterion {cid!r}: {key} must be >= {minimum}")
    return v


def normalize_criterion(raw: Any) -> dict:
    """Validate one criterion and return it with every default filled in."""
    if not isinstance(raw, dict):
        raise SpecError("each criterion must be an object")
    allowed = {"id", "statement", "judgment", "check"}
    extra = set(raw) - allowed
    cid = raw.get("id")
    if not isinstance(cid, str) or not cid:
        raise SpecError("each criterion needs a non-empty string id")
    if extra:
        raise SpecError(f"criterion {cid!r}: unknown field(s) {sorted(extra)}")
    statement = raw.get("statement", "")
    if not isinstance(statement, str):
        raise SpecError(f"criterion {cid!r}: statement must be a string")
    judgment = raw.get("judgment", False)
    if not isinstance(judgment, bool):
        raise SpecError(f"criterion {cid!r}: judgment must be true or false")
    check = raw.get("check")
    if judgment:
        if check is not None:
            raise SpecError(f"criterion {cid!r}: a judgment criterion must not have a check")
        return {"id": cid, "statement": statement, "judgment": True, "check": None}
    if not isinstance(check, dict):
        raise SpecError(f"criterion {cid!r}: needs a check object (or judgment: true)")
    return {"id": cid, "statement": statement, "judgment": False,
            "check": _normalize_check(cid, check)}


def _normalize_check(cid: str, check: dict) -> dict:
    ctype = check.get("type", "command" if ("cmd" in check or "argv" in check) else None)
    if ctype not in _CHECK_FIELDS:
        raise SpecError(f"criterion {cid!r}: check.type must be one of {sorted(_CHECK_FIELDS)}")
    extra = set(check) - _CHECK_FIELDS[ctype]
    if extra:
        raise SpecError(f"criterion {cid!r}: unknown check field(s) {sorted(extra)}")
    out: dict[str, Any] = {"type": ctype}
    has = _str_list(cid, "expect_contains", check.get("expect_contains"))
    hasnt = _str_list(cid, "expect_not_contains", check.get("expect_not_contains"))
    if ctype == "command":
        cmd, argv = check.get("cmd"), check.get("argv")
        if (cmd is None) == (argv is None):
            raise SpecError(f"criterion {cid!r}: command check needs exactly one of cmd or argv")
        if cmd is not None:
            if not isinstance(cmd, str) or not cmd.strip():
                raise SpecError(f"criterion {cid!r}: cmd must be a non-empty string")
            out["cmd"] = cmd
        else:
            if not (isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)):
                raise SpecError(f"criterion {cid!r}: argv must be a non-empty list of strings")
            out["argv"] = list(argv)
        cwd = check.get("cwd", ".")
        if not isinstance(cwd, str):
            raise SpecError(f"criterion {cid!r}: cwd must be a string")
        out["cwd"] = cwd
        out["timeout"] = _int_field(cid, "timeout", check.get("timeout"), 60, 1)
        out["expect_exit"] = _int_field(cid, "expect_exit", check.get("expect_exit"), 0)
    elif ctype == "file_contains":
        path = check.get("path")
        if not isinstance(path, str) or not path:
            raise SpecError(f"criterion {cid!r}: file_contains needs a path")
        if not has and not hasnt:
            raise SpecError(f"criterion {cid!r}: file_contains needs expect_contains or expect_not_contains")
        out["path"] = path
    else:
        url = check.get("url")
        if not isinstance(url, str) or not url:
            raise SpecError(f"criterion {cid!r}: http check needs a url")
        out["url"] = url
        method = check.get("method", "GET")
        if not isinstance(method, str):
            raise SpecError(f"criterion {cid!r}: method must be a string")
        out["method"] = method.upper()
        out["timeout"] = _int_field(cid, "timeout", check.get("timeout"), 30, 1)
        out["expect_status"] = _int_field(cid, "expect_status", check.get("expect_status"), 200)
    out["expect_contains"] = has
    out["expect_not_contains"] = hasnt
    return out


def normalize_criteria(raw_list: Any) -> list[dict]:
    if not isinstance(raw_list, list) or not raw_list:
        raise SpecError("criteria must be a non-empty list")
    out, seen = [], set()
    for r in raw_list:
        c = normalize_criterion(r)
        if c["id"] in seen:
            raise SpecError(f"duplicate criterion id {c['id']!r}")
        seen.add(c["id"])
        out.append(c)
    return out


def canonical_json(obj: Any) -> str:
    """Sorted keys, no whitespace, non-ASCII emitted raw. Identical across implementations."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def criterion_hash(normalized: dict) -> str:
    """sha256 (hex) of the canonical JSON of a normalised criterion."""
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def load_criteria(path: str) -> list[dict]:
    """Load and normalise a criteria file (.json, .yaml or .yml)."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        if path.lower().endswith((".yaml", ".yml")):
            import yaml  # lazy: only needed for YAML files

            doc = yaml.safe_load(text)
        else:
            doc = json.loads(text)
    except Exception as exc:  # noqa: BLE001 - surface any parse error as SpecError
        raise SpecError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(doc, dict) or "criteria" not in doc:
        raise SpecError("criteria file must be an object with a 'criteria' list")
    if doc.get("version", SPEC_VERSION) != SPEC_VERSION:
        raise SpecError(f"unsupported criteria version {doc.get('version')!r}")
    return normalize_criteria(doc["criteria"])
