"""Agent-facing layer: tool definitions (one source of truth), stable errors, shared operations.

``agent/tools.json`` is generated from the repo's ``spec/tools.json`` (see ``tools/sync_agent.py``)
and is the only place tool names, descriptions, input schemas and error hints are written. The
Anthropic, OpenAI and MCP formats printed by ``failfirst describe --json`` are all derived from it.
"""
from __future__ import annotations

import json
import os
from typing import Any

from . import __version__
from .core import DEFAULT_LOCK, LockError, baseline, verify
from .model import SpecError, load_criteria

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent")
CANDIDATES = ("failfirst.yaml", "failfirst.yml", "failfirst.json",
              "criteria.yaml", "criteria.yml", "criteria.json")


def load_tools() -> dict[str, Any]:
    """Return the parsed tools.json (tools plus the stable error table)."""
    with open(os.path.join(AGENT_DIR, "tools.json"), encoding="utf-8") as fh:
        return json.load(fh)


class CliError(Exception):
    """An expected failure with a stable ``code`` (FF_E_*), a message and a static hint."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    @property
    def exit_code(self) -> int:
        """Process exit status for this error code."""
        return int(load_tools()["errors"].get(self.code, {"exit": 70})["exit"])

    def payload(self) -> dict[str, Any]:
        """The ``{"error": {code, message, hint}}`` document printed with ``--json``."""
        hint = load_tools()["errors"].get(self.code, {}).get("hint", "")
        return {"error": {"code": self.code, "message": self.message, "hint": hint}}


def describe() -> dict[str, Any]:
    """Tool definitions in Anthropic, OpenAI and MCP formats, all derived from tools.json."""
    tools = load_tools()["tools"]
    return {
        "tool": "failfirst",
        "version": __version__,
        "anthropic": [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
                      for t in tools],
        "openai": [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                      "parameters": t["input_schema"]}} for t in tools],
        "mcp": [{"name": t["name"], "description": t["description"], "inputSchema": t["input_schema"]}
                for t in tools],
    }


def _check_args(schema: dict[str, Any], args: Any) -> None:
    if not isinstance(args, dict):
        raise CliError("FF_E_USAGE", "tool arguments must be an object")
    props = schema.get("properties", {})
    for key, value in args.items():
        if key not in props:
            raise CliError("FF_E_USAGE", f"unknown argument {key!r}")
        want = props[key].get("type")
        if (want == "string" and not isinstance(value, str)) or (want == "boolean" and not isinstance(value, bool)):
            raise CliError("FF_E_USAGE", f"argument {key!r} must be a {want}")


def find_criteria(criteria: str | None) -> str:
    """Resolve the criteria path, searching the default names in the working directory."""
    if criteria:
        if not os.path.exists(criteria):
            raise CliError("FF_E_NO_CRITERIA", f"criteria file not found: {criteria}")
        return criteria
    for name in CANDIDATES:
        if os.path.exists(name):
            return name
    raise CliError("FF_E_NO_CRITERIA", "no criteria file found (tried " + ", ".join(CANDIDATES) + ")")


def run_operation(name: str, args: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Run failfirst_baseline or failfirst_verify; returns (report, exit_code) or raises CliError."""
    spec = next((t for t in load_tools()["tools"] if t["name"] == name), None)
    if spec is None:
        raise CliError("FF_E_USAGE", f"unknown tool {name!r}")
    _check_args(spec["input_schema"], args)
    path = find_criteria(args.get("criteria"))
    try:
        criteria = load_criteria(path)
    except SpecError as exc:
        raise CliError("FF_E_BAD_CRITERIA", str(exc)) from exc
    except (OSError, UnicodeError) as exc:
        raise CliError("FF_E_BAD_CRITERIA", f"cannot read {path}: {getattr(exc, 'strerror', None) or exc}") from exc
    base_dir = os.path.dirname(os.path.abspath(path))
    lock = args.get("lock") or os.path.join(base_dir, DEFAULT_LOCK)
    try:
        if name == "failfirst_baseline":
            return baseline(criteria, lock, base_dir=base_dir, force=bool(args.get("force")),
                            dry_run=bool(args.get("dry_run")))
        return verify(criteria, lock, base_dir=base_dir)
    except LockError as exc:
        raise CliError(exc.code, str(exc)) from exc
    except OSError as exc:
        raise CliError("FF_E_IO", f"cannot write {lock}: {exc.strerror}") from exc
