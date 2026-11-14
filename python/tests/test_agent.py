"""Agent-readiness tests (AGENT_UX_SPEC.md items 1-6, 8): docs budget, tool definitions, schemas,
error vectors, MCP client round trip, closed stdin, NO_COLOR, process-tree kill on timeout."""
import json
import os
import signal
import subprocess
import sys
import time

import pytest

jsonschema = pytest.importorskip("jsonschema")

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "..", "src")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
AGENT = os.path.join(PKG, "failfirst", "agent")
CONF = os.path.join(REPO, "conformance", "agent")
ENV = dict(os.environ, PYTHONPATH=os.path.abspath(PKG), NO_COLOR="1", PYTHONIOENCODING="utf-8")
CLI = [sys.executable, "-m", "failfirst"]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def schema(name):
    return load(os.path.join(AGENT, "schemas", name + ".schema.json"))


MCP = load(os.path.join(CONF, "mcp-schema-2025-06-18.json"))


def mcp_validator(definition):
    return jsonschema.Draft7Validator({"$ref": "#/definitions/" + definition, "definitions": MCP["definitions"]})


def run(args, cwd, stdin=subprocess.DEVNULL, **kw):
    return subprocess.run(CLI + args, cwd=cwd, env=ENV, stdin=stdin, capture_output=True, text=True,
                          timeout=30, **kw)


def validate_output(doc):
    """Validate a parsed --json document against the schema that matches it."""
    if "error" in doc:
        name = "error"
    elif "anthropic" in doc:
        name = "describe"
    elif "phase" in doc:
        name = doc["phase"] + "-report"
    else:
        name = "version"
    jsonschema.Draft202012Validator(schema(name)).validate(doc)
    return name


# ---------------------------------------------------------------- docs and copies

def count_tokens(text):
    """tiktoken cl100k_base when available; otherwise a deliberately conservative approximation:
    max(1.5 x words, chars / 3.5). The budget test passes under both."""
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:  # noqa: BLE001 - tiktoken missing or vocabulary not downloadable
        return int(max(len(text.split()) * 1.5, len(text) / 3.5))


def test_agents_md_within_budget():
    text = open(os.path.join(AGENT, "AGENTS.md"), encoding="utf-8").read()
    assert count_tokens(text) <= 1500
    assert int(max(len(text.split()) * 1.5, len(text) / 3.5)) <= 1500  # approximation also passes


def test_llms_txt_format_and_budget():
    text = open(os.path.join(AGENT, "llms.txt"), encoding="utf-8").read()
    assert text.startswith("# failfirst\n") and "\n> " in text and "](" in text
    assert count_tokens(text) <= 600


def test_help_within_budget(tmp_path):
    out = run(["--help"], tmp_path).stdout + run(["baseline", "--help"], tmp_path).stdout
    assert count_tokens(out) <= 700


@pytest.mark.skipif(not os.path.exists(os.path.join(REPO, "tools", "sync_agent.py")), reason="not a repo checkout")
def test_packaged_copies_are_current():
    for script in ("sync_agent.py", "gen_agent_vectors.py"):
        r = subprocess.run([sys.executable, os.path.join(REPO, "tools", script), "--check"],
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------- tool definitions

def test_describe_matches_conformance_vector(tmp_path):
    r = run(["describe", "--json"], tmp_path)
    assert r.returncode == 0
    assert json.loads(r.stdout) == load(os.path.join(CONF, "describe.json"))["expected"]


def test_three_formats_validate(tmp_path):
    doc = json.loads(run(["describe", "--json"], tmp_path).stdout)
    assert validate_output(doc) == "describe"
    names = [t["name"] for t in doc["anthropic"]]
    assert names == [t["function"]["name"] for t in doc["openai"]] == [t["name"] for t in doc["mcp"]]
    for t in doc["anthropic"]:  # Anthropic tool use: name, description, input_schema (JSON Schema)
        assert set(t) == {"name", "description", "input_schema"}
        jsonschema.Draft202012Validator.check_schema(t["input_schema"])
        assert t["input_schema"]["type"] == "object"
    for t in doc["openai"]:  # OpenAI function calling: type=function, function.{name,description,parameters}
        assert set(t) == {"type", "function"} and t["type"] == "function"
        assert set(t["function"]) == {"name", "description", "parameters"}
        jsonschema.Draft202012Validator.check_schema(t["function"]["parameters"])
    mcp_validator("ListToolsResult").validate({"tools": doc["mcp"]})  # official MCP schema
    assert doc["anthropic"][0]["input_schema"] == doc["openai"][0]["function"]["parameters"] == doc["mcp"][0]["inputSchema"]


# ---------------------------------------------------------------- vectors, schemas, stdin, colour

def apply_steps(vec, cwd):
    for name, text in vec["files"].items():
        os.makedirs(os.path.dirname(os.path.join(cwd, name)) or cwd, exist_ok=True)
        with open(os.path.join(cwd, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    last = None
    for step in vec["steps"]:
        if isinstance(step, dict):
            for name, text in step["write"].items():
                with open(os.path.join(cwd, name), "w", encoding="utf-8") as fh:
                    fh.write(text)
        else:
            last = run(step, cwd)
    return last


def subset(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(actual[k], v) for k, v in expected.items())
    return actual == expected


VECTORS = load(os.path.join(CONF, "errors.json"))["vectors"]


@pytest.mark.parametrize("vec", VECTORS, ids=[v["name"] for v in VECTORS])
def test_cli_vectors(vec, tmp_path):
    r = apply_steps(vec, str(tmp_path))
    exp = vec["expected"]
    assert r.returncode == exp["exit"], r.stdout + r.stderr
    assert "\x1b" not in r.stdout + r.stderr
    if "error_code" in exp:
        doc = json.loads(r.stdout)
        assert doc["error"]["code"] == exp["error_code"]
        assert doc["error"]["message"] and doc["error"]["hint"]
        assert exp["error_code"] in r.stderr  # human copy on stderr, JSON on stdout
    if "json_contains" in exp:
        assert subset(json.loads(r.stdout), exp["json_contains"])
    if "lock_exists" in exp:
        assert os.path.exists(tmp_path / ".failfirst.lock.json") == exp["lock_exists"]
    if "stdout_lines" in exp:
        assert len(r.stdout.strip().splitlines()) == exp["stdout_lines"]
    validate_output(json.loads(r.stdout))  # EVERY --json output validates against its schema


def test_every_json_output_kind_is_schema_valid(tmp_path):
    crit = {"criteria": [{"id": "A", "check": {"cmd": "test -f flag"}},
                         {"id": "J", "judgment": True},
                         {"id": "P", "check": {"cmd": "true"}}]}
    (tmp_path / "failfirst.json").write_text(json.dumps(crit))
    kinds = set()
    for args in (["baseline", "--json"], ["verify", "--json"], ["describe", "--json"], ["--version", "--json"],
                 ["baseline", "--json"]):
        kinds.add(validate_output(json.loads(run(args, tmp_path).stdout)))
    (tmp_path / "flag").write_text("x")
    kinds.add(validate_output(json.loads(run(["verify", "--json"], tmp_path).stdout)))
    assert kinds == {"baseline-report", "verify-report", "describe", "version", "error"}


COMMANDS = [["baseline", "--json"], ["verify", "--json"], ["describe", "--json"], ["describe"], ["--version"],
            ["baseline", "--dry-run", "--quiet"], ["verify", "--quiet"], ["--help"], ["mcp"], []]


@pytest.mark.parametrize("args", COMMANDS, ids=[" ".join(a) or "no-args" for a in COMMANDS])
@pytest.mark.parametrize("mode", ["devnull", "closed"])
def test_no_command_blocks_on_stdin(args, mode, tmp_path):
    (tmp_path / "failfirst.json").write_text(json.dumps({"criteria": [{"id": "A", "check": {"cmd": "false"}}]}))
    kw = {"stdin": subprocess.DEVNULL} if mode == "devnull" else {"stdin": None, "preexec_fn": lambda: os.close(0)}
    r = subprocess.run(CLI + args, cwd=tmp_path, env=ENV, capture_output=True, text=True, timeout=20, **kw)
    assert r.returncode in (0, 1, 2, 3)
    assert "\x1b" not in r.stdout + r.stderr


# ---------------------------------------------------------------- MCP client round trip

class McpClient:
    def __init__(self, cwd):
        self.p = subprocess.Popen(CLI + ["mcp"], cwd=cwd, env=ENV, text=True, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.n = 0

    def send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        return None if notify else json.loads(self.p.stdout.readline())

    def close(self):
        self.p.stdin.close()
        assert self.p.wait(timeout=10) == 0


def test_mcp_initialize_list_call(tmp_path):
    (tmp_path / "failfirst.json").write_text(json.dumps({"criteria": [{"id": "A", "check": {"cmd": "test -f flag"}}]}))
    c = McpClient(tmp_path)
    try:
        init = c.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "pytest", "version": "1"}})
        mcp_validator("InitializeResult").validate(init["result"])
        assert init["result"]["protocolVersion"] == "2025-06-18"
        assert init["result"]["serverInfo"]["name"] == "failfirst"
        c.send("notifications/initialized", notify=True)
        tools = c.send("tools/list")["result"]
        mcp_validator("ListToolsResult").validate(tools)
        assert [t["name"] for t in tools["tools"]] == ["failfirst_baseline", "failfirst_verify"]
        res = c.send("tools/call", {"name": "failfirst_baseline", "arguments": {}})["result"]
        mcp_validator("CallToolResult").validate(res)
        assert res["isError"] is False
        report = json.loads(res["content"][0]["text"])
        assert report == res["structuredContent"] and validate_output(report) == "baseline-report"
        assert report["summary"]["failed_as_required"] == 1
        (tmp_path / "flag").write_text("x")
        res = c.send("tools/call", {"name": "failfirst_verify", "arguments": {}})["result"]
        assert res["structuredContent"]["status"] == "pass"
        # tool-level failure: isError true with {code, message, hint}
        res = c.send("tools/call", {"name": "failfirst_baseline", "arguments": {}})["result"]
        mcp_validator("CallToolResult").validate(res)
        assert res["isError"] is True and res["structuredContent"]["error"]["code"] == "FF_E_LOCK_EXISTS"
        res = c.send("tools/call", {"name": "failfirst_verify", "arguments": {"bogus": 1}})["result"]
        assert res["isError"] is True and res["structuredContent"]["error"]["code"] == "FF_E_USAGE"
        # protocol-level failures
        assert c.send("tools/call", {"name": "nope", "arguments": {}})["error"]["code"] == -32602
        assert c.send("no/such/method")["error"]["code"] == -32601
        assert c.send("ping")["result"] == {}
    finally:
        c.close()


# ---------------------------------------------------------------- timeout kills the process tree

def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@pytest.mark.skipif(os.name != "posix", reason="process groups")
def test_timeout_kills_grandchildren(tmp_path):
    crit = {"criteria": [{"id": "A", "check": {"cmd": "sleep 60 & echo $! > pid; wait", "timeout": 1}}]}
    (tmp_path / "failfirst.json").write_text(json.dumps(crit))
    r = run(["baseline", "--json"], tmp_path)
    assert json.loads(r.stdout)["criteria"][0]["baseline"]["status"] == "error"
    pid = int((tmp_path / "pid").read_text())
    for _ in range(50):
        if not _alive(pid):
            break
        time.sleep(0.1)
    if _alive(pid):
        os.kill(pid, signal.SIGKILL)
    assert not _alive(pid), "grandchild survived the timeout"
