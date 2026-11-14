"""Command line: failfirst baseline | verify | describe | mcp.

Agent-safe: never prompts, never reads stdin (except ``mcp``, which speaks the protocol on it),
never emits ANSI colour. Expected failures print ``{"error": {code, message, hint}}`` on stdout
with ``--json`` (human text on stderr otherwise) and exit 2.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, NoReturn

from . import __version__
from .agent import CliError, describe, load_tools, run_operation
from .core import DEFAULT_LOCK, format_report


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CliError("FF_E_USAGE", message)


def _dump(obj: Any, compact: bool) -> str:
    if compact:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _quiet_line(report: dict[str, Any]) -> str:
    summ = ", ".join(f"{n} {k}" for k, n in sorted(report["summary"].items()))
    return f"failfirst {report['phase']}: {report['status']} ({summ})"


def _build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="failfirst", description="Acceptance criteria that must fail before they may pass. "
                "Exit: 0 pass, 1 fail, 2 usage/input error, 3 awaiting human review, 70 internal.")
    p.add_argument("--version", action="store_true", help="print the version (with --json: {tool, version})")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", parser_class=_Parser)
    for name, helptext in (("baseline", "run criteria on the unfixed state and write the lockfile"),
                           ("verify", "re-run criteria and check they were proven")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("criteria", nargs="?", help="criteria file (.json/.yaml)")
        s.add_argument("--lock", help=f"lockfile path (default: {DEFAULT_LOCK} next to the criteria file)")
        s.add_argument("--json", action="store_true", help="print the JSON report")
        s.add_argument("--quiet", action="store_true", help="one-line summary (compact JSON with --json)")
        s.add_argument("--report", help="also write the JSON report to this file")
        if name == "baseline":
            s.add_argument("--force", action="store_true", help="overwrite an existing lockfile")
            s.add_argument("--dry-run", action="store_true", help="run and report, write no lockfile or report file")
    d = sub.add_parser("describe", help="print tool definitions (Anthropic, OpenAI, MCP)")
    d.add_argument("--json", action="store_true", help="print the definitions as JSON")
    d.add_argument("--quiet", action="store_true", help="compact JSON")
    m = sub.add_parser("mcp", help="run an MCP server on stdio")
    m.add_argument("--json", action="store_true", help="accepted and ignored; MCP is always JSON-RPC")
    return p


def _run(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    if args.version:
        print(_dump({"tool": "failfirst", "version": __version__}, False) if args.json
              else f"failfirst {__version__}")
        return 0
    if args.cmd is None:
        raise CliError("FF_E_USAGE", "a command is required (baseline, verify, describe, mcp)")
    quiet, as_json = getattr(args, "quiet", False), args.json
    if args.cmd == "describe":
        doc = describe()
        if as_json:
            print(_dump(doc, quiet))
        else:
            for t in load_tools()["tools"]:
                print(f"{t['name']}: {t['description'].split('. ')[0].rstrip('.')}.")
        return 0
    if args.cmd == "mcp":
        from .mcp import serve
        return serve()
    tool_args: dict[str, Any] = {}
    if args.criteria:
        tool_args["criteria"] = args.criteria
    if args.lock:
        tool_args["lock"] = args.lock
    if args.cmd == "baseline":
        tool_args.update(force=args.force, dry_run=args.dry_run)
    report, code = run_operation("failfirst_" + args.cmd, tool_args)
    if args.report and not (args.cmd == "baseline" and args.dry_run):
        try:
            with open(args.report, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            raise CliError("FF_E_IO", f"cannot write {args.report}: {exc.strerror}") from exc
    if as_json:
        print(_dump(report, quiet))
    else:
        print(_quiet_line(report) if quiet else format_report(report))
    return code


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit status."""
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    try:
        return _run(args)
    except CliError as exc:
        err = exc
    except Exception as exc:  # noqa: BLE001 - never leak a bare stack trace
        err = CliError("FF_E_INTERNAL", f"{type(exc).__name__}: {exc}")
    info = err.payload()["error"]
    print(f"failfirst: {info['code']}: {info['message']}\n  hint: {info['hint']}", file=sys.stderr)
    if as_json:
        print(_dump(err.payload(), False))
    return err.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
