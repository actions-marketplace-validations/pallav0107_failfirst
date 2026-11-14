#!/usr/bin/env python3
"""Agent task eval (AGENT_UX_SPEC.md item 8): can an open-weight model use this tool from docs alone?

The model sees ONLY: llms.txt + AGENTS.md (system prompt), the tool definitions printed by
`<tool> describe --json` (OpenAI format) plus three sandbox helpers (write_file, read_file,
run_command), and the task text. No source code, no hints.

Fixed settings (set before any run, see AGENT_UX_SPEC.md):
  endpoint http://localhost:11434/v1 (Ollama, OpenAI-compatible), primary model gpt-oss:20b,
  secondary glm-4.7-flash, 3 runs per task, temperature 0.2, at most 20 tool calls per run,
  fresh sandbox per run, pass bar 80% of (task x run) attempts for the PRIMARY model.
Success is decided ONLY by each task's machine `checks` (files, exit codes, outputs), never by
the model. Full transcripts and a scores JSON are written to --out.

Task files: eval/agent_tasks/*.yaml, keys: id, prompt, files (path->content), setup (shell
commands run in the sandbox before the agent starts), checks (list). Check types:
  file_exists {path} | file_contains {path, text} | file_not_contains {path, text}
  command {cmd, expect_exit=0, expect_stdout_contains=None}   (run in the sandbox after the run)
  tool_called {name}   (the agent invoked that tool-definition tool or ran it via run_command)

Usage:  python eval/run_agent_eval.py --cmd "failfirst"            # real run (GPU needed)
        python eval/run_agent_eval.py --list                       # list tasks, no model call
Not run by the test suite against a real model; tests use a scripted stub endpoint.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODELS = ["gpt-oss:20b", "glm-4.7-flash"]
PRIMARY_INDEX = 0
RUNS = 3
TEMPERATURE = 0.2
MAX_TOOL_CALLS = 20
PASS_BAR = 0.80
CMD_TIMEOUT = 60

SANDBOX_TOOLS = [
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a text file in the working directory.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "relative path"},
            "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a text file in the working directory.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_command", "description": "Run a shell command in the working directory (no stdin). Returns exit code and output.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]


def load_tasks(task_dir: str, only: list[str] | None = None) -> list[dict]:
    import yaml
    tasks = []
    for path in sorted(glob.glob(os.path.join(task_dir, "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            task = yaml.safe_load(fh)
        task.setdefault("files", {})
        task.setdefault("setup", [])
        if only and task["id"] not in only:
            continue
        tasks.append(task)
    return tasks


def _safe(sandbox: str, rel: str) -> str:
    full = os.path.realpath(os.path.join(sandbox, rel))
    if full != os.path.realpath(sandbox) and not full.startswith(os.path.realpath(sandbox) + os.sep):
        raise ValueError("path escapes the sandbox")
    return full


def make_sandbox(task: dict, tool_cmd: str, tool_name: str) -> tuple[str, dict]:
    sandbox = tempfile.mkdtemp(prefix="agenteval-")
    bindir = os.path.join(sandbox, ".bin")
    os.makedirs(bindir)
    shim = os.path.join(bindir, tool_name)
    with open(shim, "w", encoding="utf-8") as fh:
        fh.write(f"#!/bin/sh\nexec {tool_cmd} \"$@\"\n")
    os.chmod(shim, os.stat(shim).st_mode | stat.S_IXUSR)
    env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""), NO_COLOR="1")
    for rel, text in task["files"].items():
        full = _safe(sandbox, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)
    for cmd in task["setup"]:
        subprocess.run(cmd, shell=True, cwd=sandbox, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=CMD_TIMEOUT, check=False)
    return sandbox, env


class McpClient:
    """Minimal stdio MCP client used to execute the tool-definition tools."""

    def __init__(self, tool_cmd: str, cwd: str, env: dict):
        self.proc = subprocess.Popen(shlex.split(tool_cmd) + ["mcp"], cwd=cwd, env=env, text=True,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._id = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "agent-eval", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, msg: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("mcp server closed")
        return json.loads(line)

    def call(self, name: str, args: dict) -> str:
        resp = self.request("tools/call", {"name": name, "arguments": args})
        if "error" in resp:
            return json.dumps(resp["error"])
        return "".join(c.get("text", "") for c in resp["result"]["content"])

    def close(self) -> None:
        try:
            assert self.proc.stdin is not None
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            self.proc.kill()


def tool_definitions(tool_cmd: str, cwd: str, env: dict) -> list[dict]:
    out = subprocess.run(shlex.split(tool_cmd) + ["describe", "--json"], cwd=cwd, env=env,
                         stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=CMD_TIMEOUT, check=True)
    return json.loads(out.stdout)["openai"]


def chat(endpoint: str, model: str, messages: list[dict], tools: list[dict]) -> dict:
    body = json.dumps({"model": model, "messages": messages, "tools": tools,
                       "temperature": TEMPERATURE}).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["choices"][0]["message"]


def execute(call_name: str, args: dict, sandbox: str, env: dict, mcp: McpClient, mcp_names: set[str]) -> str:
    try:
        if call_name == "write_file":
            full = _safe(sandbox, args["path"])
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(args["content"])
            return f"wrote {args['path']}"
        if call_name == "read_file":
            with open(_safe(sandbox, args["path"]), encoding="utf-8") as fh:
                return fh.read()[:20000]
        if call_name == "run_command":
            r = subprocess.run(args["command"], shell=True, cwd=sandbox, env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=CMD_TIMEOUT)
            return json.dumps({"exit_code": r.returncode, "output": (r.stdout + r.stderr)[:20000]})
        if call_name in mcp_names:
            return mcp.call(call_name, args)
        return json.dumps({"error": f"unknown tool {call_name}"})
    except Exception as exc:  # noqa: BLE001 - tool errors are returned to the model
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


def run_checks(task: dict, sandbox: str, env: dict, calls: list[dict]) -> list[dict]:
    results = []
    for chk in task["checks"]:
        kind, ok, why = chk["type"], False, ""
        if kind in ("file_exists", "file_contains", "file_not_contains"):
            full = os.path.join(sandbox, chk["path"])
            if not os.path.exists(full):
                ok, why = kind == "file_not_contains", "missing file"
            elif kind == "file_exists":
                ok = True
            else:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                ok = (chk["text"] in text) == (kind == "file_contains")
                why = "" if ok else f"text check failed on {chk['path']}"
        elif kind == "command":
            r = subprocess.run(chk["cmd"], shell=True, cwd=sandbox, env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=CMD_TIMEOUT)
            want = chk.get("expect_exit", 0)
            ok = r.returncode == want
            needle = chk.get("expect_stdout_contains")
            if ok and needle is not None:
                ok = needle in r.stdout
            why = "" if ok else f"exit {r.returncode} (want {want}); stdout={r.stdout[-200:]!r}"
        elif kind == "tool_called":
            name = chk["name"]
            # The MCP tool is `failfirst_verify` but the shell CLI spelling is `failfirst verify`
            # (underscore -> space): accept either spelling when the call was made via run_command.
            spellings = {name, name.replace("_", " ")}
            ok = any(c["name"] == name or (c["name"] == "run_command"
                     and any(sp in str(c["args"].get("command", "")) for sp in spellings))
                     for c in calls)
            why = "" if ok else f"{name} never called"
        else:
            why = f"unknown check type {kind}"
        results.append({"check": chk, "ok": ok, "why": why})
    return results


def run_one(endpoint: str, model: str, task: dict, tool_cmd: str, tool_name: str, system: str) -> dict:
    sandbox, env = make_sandbox(task, tool_cmd, tool_name)
    transcript: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": task["prompt"]}]
    calls: list[dict] = []
    error = None
    mcp = None
    try:
        defs = tool_definitions(tool_cmd, sandbox, env)
        mcp_names = {d["function"]["name"] for d in defs}
        mcp = McpClient(tool_cmd, sandbox, env)
        tools = defs + SANDBOX_TOOLS
        while len(calls) < MAX_TOOL_CALLS:
            msg = chat(endpoint, model, transcript, tools)
            transcript.append(msg)
            tcs = msg.get("tool_calls") or []
            if not tcs:
                break
            for tc in tcs:
                if len(calls) >= MAX_TOOL_CALLS:
                    break
                fn = tc["function"]
                raw = fn.get("arguments") or {}
                try:
                    args = json.loads(raw) if isinstance(raw, str) else raw
                except ValueError:
                    args = {}
                calls.append({"name": fn["name"], "args": args})
                result = execute(fn["name"], args, sandbox, env, mcp, mcp_names)
                transcript.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": fn["name"], "content": result})
    except Exception as exc:  # noqa: BLE001 - recorded; a crashed run counts as a failure
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if mcp:
            mcp.close()
    checks = run_checks(task, sandbox, env, calls)
    passed = error is None and all(c["ok"] for c in checks)
    shutil.rmtree(sandbox, ignore_errors=True)
    return {"task": task["id"], "model": model, "passed": passed, "error": error,
            "tool_calls": len(calls), "checks": checks, "transcript": transcript}


def read_doc(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cmd", default=None, help="command that runs the tool under test (default: tool name on PATH)")
    ap.add_argument("--tool", default=None, help="tool name (default: read from repo tools.json)")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS), help="comma list; first is PRIMARY")
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--tasks", default=os.path.join(HERE, "agent_tasks"))
    ap.add_argument("--only", default="", help="comma list of task ids")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--list", action="store_true", help="list tasks and exit (no model call)")
    args = ap.parse_args(argv)

    with open(os.path.join(ROOT, "spec", "tools.json"), encoding="utf-8") as fh:
        tool_name = args.tool or json.load(fh)["tool"]
    tool_cmd = args.cmd or tool_name
    tasks = load_tasks(args.tasks, [t for t in args.only.split(",") if t])
    if args.list:
        for t in tasks:
            print(t["id"])
        return 0
    models = [m for m in args.models.split(",") if m]
    system = ("You are an autonomous agent working in a sandbox directory. Use the provided tools to complete "
              "the user's task, then reply briefly. Documentation for the tool you will use follows.\n\n"
              "=== llms.txt ===\n" + read_doc("llms.txt") + "\n=== AGENTS.md ===\n" + read_doc("AGENTS.md"))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    outdir = os.path.join(args.out, f"{tool_name}-{stamp}")
    os.makedirs(outdir, exist_ok=True)
    scores: dict = {"tool": tool_name, "endpoint": args.endpoint, "temperature": TEMPERATURE,
                    "runs_per_task": args.runs, "max_tool_calls": MAX_TOOL_CALLS, "pass_bar": PASS_BAR,
                    "primary_model": models[PRIMARY_INDEX], "system_prompt": system, "models": {}}
    for model in models:
        per_task: dict = {}
        attempts = passes = 0
        for task in tasks:
            results = []
            for i in range(args.runs):
                res = run_one(args.endpoint, model, task, tool_cmd, tool_name, system)
                with open(os.path.join(outdir, re.sub(r"[^\w.-]", "_", f"{model}__{task['id']}__run{i + 1}.json")),
                          "w", encoding="utf-8") as fh:
                    json.dump(res, fh, indent=2)
                results.append(res["passed"])
                print(f"{model} {task['id']} run{i + 1}: {'PASS' if res['passed'] else 'FAIL'}", flush=True)
            per_task[task["id"]] = {"prompt": task["prompt"], "runs": results, "passed": sum(results)}
            attempts += len(results)
            passes += sum(results)
        rate = passes / attempts if attempts else 0.0
        scores["models"][model] = {"tasks": per_task, "attempts": attempts, "passes": passes,
                                   "success_rate": rate, "meets_bar": rate >= PASS_BAR}
    with open(os.path.join(outdir, "scores.json"), "w", encoding="utf-8") as fh:
        json.dump(scores, fh, indent=2)
    primary = scores["models"][models[PRIMARY_INDEX]]
    print(f"PRIMARY {models[PRIMARY_INDEX]}: {primary['passes']}/{primary['attempts']} "
          f"= {primary['success_rate']:.0%} (bar {PASS_BAR:.0%}) -> {outdir}")
    return 0 if primary["meets_bar"] else 1


if __name__ == "__main__":
    sys.exit(main())
