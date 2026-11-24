"""Tests for the failfirst Hermes plugin (stdlib unittest, loads plugin by file path)."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

PLUGIN = Path(__file__).resolve().parent.parent
BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
CRIT = {"version": 1, "criteria": [
    {"id": "add-works", "statement": "add(2, 3) returns 5",
     "check": {"cmd": "python3 -c \"from calc import add; assert add(2, 3) == 5\""}}]}
VACUOUS = {"version": 1, "criteria": [
    {"id": "always", "statement": "vacuous", "check": {"cmd": "python3 -c \"import calc\""}}]}


class Ctx:
    def __init__(self) -> None:
        self.commands: Dict[str, Any] = {}
        self.hooks: Dict[str, List[Any]] = {}

    def register_command(self, name: str, handler: Any = None, **kw: Any) -> None:
        self.commands[name] = handler

    def register_hook(self, name: str, cb: Any, **kw: Any) -> None:
        self.hooks.setdefault(name, []).append(cb)


def load_plugin(name: str = "ff_hermes_test") -> Any:
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(shutil.which("failfirst"), "failfirst CLI not on PATH")
class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.home = tempfile.mkdtemp(prefix="ffh_home_")
        self.old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.home
        self.old_cwd = os.getcwd()
        self.addCleanup(self._cleanup)
        self.mod = load_plugin()
        self.ctx = Ctx()
        self.mod.register(self.ctx)

    def _cleanup(self) -> None:
        os.chdir(self.old_cwd)
        if self.old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_home
        shutil.rmtree(self.home, ignore_errors=True)

    def toy(self, crit: Dict[str, Any]) -> Path:
        d = Path(tempfile.mkdtemp(prefix="ffh_toy_")).resolve()
        self.addCleanup(shutil.rmtree, str(d), True)
        (d / "calc.py").write_text(BUGGY)
        (d / "failfirst.json").write_text(json.dumps(crit, indent=2))
        return d

    def baseline(self, d: Path, sid: str = "S1") -> str:
        os.chdir(d)
        out = self.ctx.commands["failfirst"](f"baseline {d / 'failfirst.json'}", session_id=sid)
        os.chdir(self.old_cwd)
        return str(out)

    def gate(self, out: str) -> str:
        lines = [ln for ln in out.splitlines() if ln.startswith("/goal gate add ")]
        self.assertEqual(len(lines), 1, out)
        return lines[0][len("/goal gate add "):]

    def run_gate(self, cmd: str, d: Path) -> int:
        return subprocess.run(cmd, shell=True, cwd=str(d), capture_output=True).returncode

    def blocked(self, sid: str, tool: str, args: Dict[str, Any]) -> bool:
        for cb in self.ctx.hooks["pre_tool_call"]:
            res = cb(tool_name=tool, args=args, task_id="", session_id=sid,
                     conversation_id=sid, tool_call_id="t", turn_id="u")
            if isinstance(res, dict) and res.get("action") == "block" and res.get("message"):
                return True
        return False


class GateTests(Base):
    def test_gate_fails_before_and_passes_after_fix(self) -> None:
        d = self.toy(CRIT)
        cmd = self.gate(self.baseline(d))
        self.assertNotEqual(self.run_gate(cmd, d), 0)
        (d / "calc.py").write_text(FIXED)
        self.assertEqual(self.run_gate(cmd, d), 0)

    def test_vacuous_criteria_refused(self) -> None:
        d = self.toy(VACUOUS)
        out = self.baseline(d)
        self.assertNotIn("/goal gate add", out)
        self.assertIn("vacuous", out.lower())
        self.assertIn("always", out)
        self.assertFalse((d / ".failfirst.lock.json").exists())

    def test_lock_tamper_fails_gate(self) -> None:
        d = self.toy(CRIT)
        cmd = self.gate(self.baseline(d))
        (d / "calc.py").write_text(FIXED)
        lock = d / ".failfirst.lock.json"
        orig = lock.read_bytes()
        lock.write_bytes(orig + b"\n")
        self.assertNotEqual(self.run_gate(cmd, d), 0)
        lock.write_bytes(orig)
        self.assertEqual(self.run_gate(cmd, d), 0)

    def test_weakened_criterion_fails_gate(self) -> None:
        d = self.toy(CRIT)
        cmd = self.gate(self.baseline(d))
        (d / "calc.py").write_text(FIXED)
        weak = json.loads(json.dumps(CRIT))
        weak["criteria"][0]["check"]["cmd"] = "true"
        (d / "failfirst.json").write_text(json.dumps(weak))
        self.assertNotEqual(self.run_gate(cmd, d), 0)

    def test_status_reports_gate(self) -> None:
        d = self.toy(CRIT)
        self.baseline(d)
        self.assertIn("FAIL", self.ctx.commands["failfirst"]("status", session_id="S1"))
        (d / "calc.py").write_text(FIXED)
        self.assertIn("PASS", self.ctx.commands["failfirst"]("status", session_id="S1"))

    def test_help_and_unprotected_status(self) -> None:
        self.assertIn("/failfirst baseline", self.ctx.commands["failfirst"](""))
        self.assertIn("baseline", self.ctx.commands["failfirst"]("status", session_id="none"))


class HookTests(Base):
    def setUp(self) -> None:
        super().setUp()
        self.d = self.toy(CRIT)
        self.baseline(self.d)
        self.crit = str(self.d / "failfirst.json")
        self.lock = str(self.d / ".failfirst.lock.json")

    def test_blocks(self) -> None:
        cases = [
            ("write_file", {"path": self.crit, "content": "{}"}),
            ("write_file", {"path": "failfirst.json", "content": "{}"}),
            ("write_file", {"path": "./sub/../failfirst.json", "content": "{}"}),
            ("patch", {"path": self.lock, "old_string": "a", "new_string": "b"}),
            ("patch", {"mode": "patch", "patch": "*** Begin Patch\n*** Update File: failfirst.json\n@@\n-a\n+b\n*** End Patch"}),
            ("patch", {"mode": "patch", "patch": f"*** Begin Patch\n*** Delete File: {self.lock}\n*** End Patch"}),
            ("patch", {"mode": "patch", "patch": "*** Begin Patch\n*** Update File: calc.py\n*** Move to: failfirst.json\n*** End Patch"}),
            ("terminal", {"command": "failfirst baseline --force"}),
            ("terminal", {"command": "rm .failfirst.lock.json"}),
            ("terminal", {"command": f"echo '{{}}' > {self.crit}"}),
            ("terminal", {"command": "echo x >> failfirst.json"}),
            ("terminal", {"command": "sed -i s/a/b/ failfirst.json"}),
            ("terminal", {"command": "git checkout -- failfirst.json"}),
            ("terminal", {"command": "python3 -c \"open('failfirst.json','w').write('{}')\""}),
        ]
        for tool, args in cases:
            with self.subTest(tool=tool, args=args):
                self.assertTrue(self.blocked("S1", tool, args))

    def test_allows(self) -> None:
        cases = [
            ("terminal", {"command": "python3 -m pytest -q"}),
            ("write_file", {"path": str(self.d / "calc.py"), "content": FIXED}),
            ("write_file", {"path": "calc.py", "content": FIXED}),
            ("terminal", {"command": "cat failfirst.json"}),
            ("terminal", {"command": "grep add failfirst.json .failfirst.lock.json"}),
            ("terminal", {"command": "failfirst verify failfirst.json --quiet"}),
            ("patch", {"mode": "patch", "patch": "*** Begin Patch\n*** Update File: calc.py\n@@\n-a\n+b\n*** End Patch"}),
            ("some_other_tool", {"path": self.crit}),
        ]
        for tool, args in cases:
            with self.subTest(tool=tool, args=args):
                self.assertFalse(self.blocked("S1", tool, args))

    def test_execute_code(self) -> None:
        bad = "open('.failfirst.lock.json', 'w').write('{}')"
        self.assertTrue(self.blocked("S1", "execute_code", {"code": bad}))
        self.assertTrue(self.blocked("S1", "execute_code",
                                     {"code": "write_file('failfirst.json', '{}')"}))
        self.assertFalse(self.blocked("S1", "execute_code",
                                      {"code": "print(open('failfirst.json').read())"}))
        self.assertFalse(self.blocked("S1", "execute_code",
                                      {"code": "open('calc.py', 'w').write('x')"}))

    def test_protection_follows_compression_rotation(self) -> None:
        hook = self.ctx.hooks["pre_tool_call"][0]
        args = {"path": self.crit, "content": "{}"}
        # First tool call after baseline: physical id S1, conversation root R.
        self.assertIsNotNone(hook(tool_name="write_file", args=args, session_id="S1",
                                  conversation_id="R"))
        # Compression rotates the session id; only the root stays.
        res = hook(tool_name="write_file", args=args, session_id="S1-child", conversation_id="R")
        self.assertEqual(res["action"], "block")
        self.ctx.commands["failfirst"]("release", session_id="S1")
        self.assertIsNone(hook(tool_name="write_file", args=args, session_id="S1-child",
                               conversation_id="R"))

    def test_guard_never_raises(self) -> None:
        self.mod._store._SESSIONS["S9"] = {"criteria": self.crit}  # malformed record
        hook = self.ctx.hooks["pre_tool_call"][0]
        self.assertIsNone(hook(tool_name="terminal", args={"command": "rm x"}, session_id="S9"))

    def test_unprotected_session_never_blocked(self) -> None:
        self.assertFalse(self.blocked("S2", "write_file", {"path": self.crit, "content": "{}"}))

    def test_release(self) -> None:
        out = self.ctx.commands["failfirst"]("release", session_id="S1")
        self.assertIn("released", out)
        self.assertFalse(self.blocked("S1", "write_file", {"path": self.crit, "content": "{}"}))
        self.assertEqual(json.loads(self.mod._store.store_path().read_text()), {})


class PreVerifyTests(Base):
    def test_red_turn_is_kept_going_until_green(self) -> None:
        d = self.toy(CRIT)
        self.baseline(d)
        hook = self.ctx.hooks["pre_verify"][0]
        kw = dict(platform="cli", model="m", coding=True, attempt=0,
                  final_response="done", changed_paths=["calc.py"])
        res = hook(session_id="S1", **kw)
        self.assertEqual(res["action"], "continue")
        self.assertIn("not proven", res["message"])
        (d / "calc.py").write_text(FIXED)
        self.assertIsNone(hook(session_id="S1", **kw))
        self.assertIsNone(hook(session_id="S2", **kw))  # unprotected session


class SessionTests(Base):
    def test_no_session_refused_before_baseline(self) -> None:
        d = self.toy(CRIT)
        os.chdir(d)
        out = self.ctx.commands["failfirst"](f"baseline {d / 'failfirst.json'}", session_id="")
        os.chdir(self.old_cwd)
        self.assertNotIn("/goal gate add", out)
        self.assertIn("no session", out)
        self.assertFalse((d / ".failfirst.lock.json").exists())

    def test_existing_lock_gets_hint(self) -> None:
        d = self.toy(CRIT)
        (d / ".failfirst.lock.json").write_text("{}")
        out = self.baseline(d)
        self.assertNotIn("/goal gate add", out)
        self.assertIn("delete it yourself", out)
        self.assertEqual((d / ".failfirst.lock.json").read_text(), "{}")  # never deleted

    def test_corrupt_records_ignored_on_load(self) -> None:
        path = Path(self.home) / "failfirst" / "sessions.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"S1": {"criteria": "x"}}))
        self.assertEqual(self.mod._store.load(), {})


class PersistenceTests(Base):
    def test_protection_survives_reload(self) -> None:
        d = self.toy(CRIT)
        self.baseline(d)
        sessions = Path(self.home) / "failfirst" / "sessions.json"
        self.assertTrue(sessions.is_file())
        mod2, ctx2 = load_plugin("ff_hermes_test2"), Ctx()
        mod2.register(ctx2)
        res = ctx2.hooks["pre_tool_call"][0](
            tool_name="write_file", args={"path": str(d / "failfirst.json"), "content": "x"},
            session_id="S1", conversation_id="")
        self.assertEqual(res["action"], "block")


if __name__ == "__main__":
    unittest.main()
