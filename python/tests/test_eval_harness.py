"""The agent-eval harness is tested against a scripted stub endpoint; no real model is called."""
import http.server
import importlib.util
import json
import os
import shlex
import sys
import threading

import pytest

pytest.importorskip("yaml")
HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.abspath(os.path.join(HERE, "..", "..", "eval"))
if not os.path.exists(os.path.join(EVAL, "run_agent_eval.py")):
    pytest.skip("eval harness not in this checkout", allow_module_level=True)
spec = importlib.util.spec_from_file_location("run_agent_eval", os.path.join(EVAL, "run_agent_eval.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def tool_call(name, args, i):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


class Stub:
    def __init__(self, script):
        self.script, self.requests = list(script), []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                msg = outer.script.pop(0) if outer.script else {"role": "assistant", "content": "done"}
                data = json.dumps({"choices": [{"message": msg}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}/v1"


def run_eval(tmp_path, monkeypatch, script):
    monkeypatch.setenv("PYTHONPATH", os.path.abspath(os.path.join(HERE, "..", "src")))
    stub = Stub(script)
    code = mod.main(["--cmd", f"{shlex.quote(sys.executable)} -m failfirst", "--endpoint", stub.url, "--models", "stub", "--runs", "1",
                     "--only", "prove-fix", "--out", str(tmp_path)])
    scores = json.load(open(next(tmp_path.glob("*/scores.json"))))
    return code, scores, stub


def test_tasks_load_and_have_checks():
    tasks = mod.load_tasks(os.path.join(EVAL, "agent_tasks"))
    assert len(tasks) >= 5
    for t in tasks:
        assert t["prompt"] and t["checks"], t["id"]


def test_fixed_settings():
    assert (mod.DEFAULT_ENDPOINT, mod.DEFAULT_MODELS, mod.RUNS, mod.TEMPERATURE, mod.MAX_TOOL_CALLS) == (
        "http://localhost:11434/v1", ["gpt-oss:20b", "glm-4.7-flash"], 3, 0.2, 20)


def test_success_decided_by_machine_check(tmp_path, monkeypatch):
    fix = tool_call("write_file", {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}, 1)
    ver = tool_call("failfirst_verify", {}, 2)
    code, scores, stub = run_eval(tmp_path, monkeypatch, [fix, ver, {"role": "assistant", "content": "fixed"}])
    assert code == 0 and scores["models"]["stub"]["passes"] == 1
    req = stub.requests[0]
    assert req["temperature"] == 0.2
    names = [t["function"]["name"] for t in req["tools"]]
    assert "failfirst_verify" in names and "write_file" in names
    assert "=== AGENTS.md ===" in req["messages"][0]["content"]


def test_model_claim_without_fix_fails(tmp_path, monkeypatch):
    code, scores, _ = run_eval(tmp_path, monkeypatch, [{"role": "assistant", "content": "All fixed, trust me."}])
    assert code == 1 and scores["models"]["stub"]["passes"] == 0


def test_tool_call_cap(tmp_path, monkeypatch):
    spin = [tool_call("read_file", {"path": "calc.py"}, i) for i in range(40)]
    _, scores, stub = run_eval(tmp_path, monkeypatch, spin)
    assert len(stub.requests) == mod.MAX_TOOL_CALLS
