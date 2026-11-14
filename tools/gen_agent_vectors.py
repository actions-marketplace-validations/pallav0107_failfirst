#!/usr/bin/env python3
"""Write conformance/agent/describe.json (expected `describe --json` output) from spec/tools.json.

`--check` fails if the committed file is out of date. errors.json is hand-written.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def expected() -> dict:
    tools = json.load(open(os.path.join(ROOT, "spec", "tools.json"), encoding="utf-8"))["tools"]
    version = re.search(r'__version__ = "([^"]+)"',
                        open(os.path.join(ROOT, "python", "src", "failfirst", "__init__.py"), encoding="utf-8").read()).group(1)
    return {
        "description": "Expected output of `failfirst describe --json`; every implementation must match it exactly.",
        "expected": {
            "tool": "failfirst", "version": version,
            "anthropic": [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in tools],
            "openai": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools],
            "mcp": [{"name": t["name"], "description": t["description"], "inputSchema": t["input_schema"]} for t in tools],
        },
    }


def main() -> int:
    path = os.path.join(ROOT, "conformance", "agent", "describe.json")
    text = json.dumps(expected(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        ok = os.path.exists(path) and open(path, encoding="utf-8", newline="").read() == text
        print("ok" if ok else "STALE conformance/agent/describe.json")
        return 0 if ok else 1
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
