"""Minimal MCP server over stdio (newline-delimited JSON-RPC 2.0): ``failfirst mcp``.

Exposes the tools in tools.json. Implements initialize, ping, tools/list and tools/call; other
requests get JSON-RPC error -32601. Never reads anything but the protocol stream.
"""
from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from . import __version__
from .agent import CliError, describe, run_operation

SUPPORTED = ("2025-06-18", "2025-03-26", "2024-11-05")


def _result(rid: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _call(params: dict[str, Any]) -> dict[str, Any]:
    name, args = params.get("name"), params.get("arguments") or {}
    try:
        report, _code = run_operation(str(name), args)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        return {"content": [{"type": "text", "text": text}], "structuredContent": report, "isError": False}
    except CliError as exc:
        payload = exc.payload()
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
                "structuredContent": payload, "isError": True}


def handle(msg: Any) -> dict[str, Any] | None:
    """Handle one decoded JSON-RPC message; returns the response, or None for notifications."""
    if not isinstance(msg, dict) or "method" not in msg:
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
    if "id" not in msg:
        return None
    rid, method, params = msg["id"], msg["method"], msg.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _result(rid, {"protocolVersion": asked if asked in SUPPORTED else SUPPORTED[0],
                             "capabilities": {"tools": {}},
                             "serverInfo": {"name": "failfirst", "version": __version__}})
    if method == "ping":
        return _result(rid, {})
    if method == "tools/list":
        return _result(rid, {"tools": describe()["mcp"]})
    if method == "tools/call":
        if not isinstance(params, dict) or params.get("name") not in {t["name"] for t in describe()["mcp"]}:
            return _error(rid, -32602, f"unknown tool {params.get('name')!r}")
        return _result(rid, _call(params))
    return _error(rid, -32601, f"method not found: {method}")


def serve(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    """Serve until stdin closes."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    if stdin is None or stdout is None:  # a closed standard stream: nothing to serve
        return 0
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line))
        except ValueError:
            reply = _error(None, -32700, "parse error")
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False, separators=(",", ":")) + "\n")
            stdout.flush()
    return 0
