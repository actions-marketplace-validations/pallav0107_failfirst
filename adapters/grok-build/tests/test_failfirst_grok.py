"""Tests for failfirst_grok.py. Each test runs the script as a subprocess with a temp GROK_HOME."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "failfirst_grok.py"
BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
CRIT = {"version": 1, "criteria": [
    {"id": "add-works", "statement": "add(2, 3) returns 5",
     "check": {"cmd": "python3 -c \"from calc import add; assert add(2, 3) == 5\""}}]}
VACUOUS = {"version": 1, "criteria": [
    {"id": "always", "statement": "vacuous", "check": {"cmd": "python3 -c \"import calc\""}}]}


def _have_failfirst() -> bool:
    return shutil.which("failfirst") is not None


@unittest.skipUnless(_have_failfirst(), "failfirst CLI not on PATH")
class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.home = tempfile.mkdtemp(prefix="ffg_home_")
        self.env = {**os.environ, "GROK_HOME": self.home, "PYTHONDONTWRITEBYTECODE": "1"}
        self.addCleanup(shutil.rmtree, self.home, True)

    def ff(self, args, cwd, stdin=None, env=None):
        return subprocess.run([sys.executable, str(SCRIPT)] + args, cwd=str(cwd), input=stdin,
                              capture_output=True, text=True, env=env or self.env, timeout=300)

    def toy(self, crit=CRIT) -> Path:
        d = Path(tempfile.mkdtemp(prefix="ffg_toy_")).resolve()
        self.addCleanup(shutil.rmtree, d, True)
        (d / "calc.py").write_text(BUGGY)
        (d / "failfirst.json").write_text(json.dumps(crit))
        return d

    def baselined(self) -> Path:
        d = self.toy()
        self.assertEqual(self.ff(["baseline"], d).returncode, 0)
        return d

    def payload(self, d, event, sid="s1", **extra) -> str:
        base = {"hookEventName": event, "sessionId": sid, "cwd": str(d), "workspaceRoot": str(d)}
        base.update(extra)
        return json.dumps(base)

    def tool(self, d, name, inp):
        return self.ff(["hook", "pre-tool-use"], d,
                       self.payload(d, "pre_tool_use", toolName=name, toolInput=inp))

    def stop(self, d, sid="s1", reason="end_turn", env=None):
        return self.ff(["hook", "stop"], d,
                       self.payload(d, "stop", sid, reason=reason), env=env)

    def cmd(self, d, command):
        return self.tool(d, "run_terminal_command", {"command": command})


class BaselineTests(Base):
    def test_clean_baseline_records_workspace(self):
        d = self.baselined()
        self.assertTrue((d / ".failfirst.lock.json").is_file())
        rec = json.loads((Path(self.home) / "failfirst" / "workspaces.json").read_text())
        self.assertIn(str(d), rec)

    def test_vacuous_refused_without_lock(self):
        d = self.toy(VACUOUS)
        r = self.ff(["baseline"], d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("vacuous", (r.stdout + r.stderr).lower())
        self.assertIn("always", r.stdout)
        self.assertFalse((d / ".failfirst.lock.json").exists())
        self.assertNotEqual(self.tool(d, "write", {"file_path": "failfirst.json"}).returncode, 2)

    def test_release_drops_record(self):
        d = self.baselined()
        self.assertEqual(self.ff(["release"], d).returncode, 0)
        self.assertEqual(self.tool(d, "write", {"file_path": "failfirst.json"}).returncode, 0)


class PreToolUseTests(Base):
    def test_denied_calls(self):
        d = self.baselined()
        denied = [("write", {"file_path": "failfirst.json", "content": "{}"}),
                  ("write", {"file_path": str(d / "failfirst.json"), "content": "{}"}),
                  ("search_replace", {"file_path": str(d / ".failfirst.lock.json"),
                                      "old_string": "a", "new_string": "b"}),
                  ("run_terminal_command", {"command": "failfirst baseline --force"}),
                  ("run_terminal_command", {"command": "rm .failfirst.lock.json"}),
                  ("run_terminal_command", {"command": "echo '{}' > failfirst.json"}),
                  ("run_terminal_command", {"command": "sed -i s/a/b/ failfirst.json"}),
                  ("run_terminal_command", {"command": "git checkout failfirst.json"}),
                  ("run_terminal_command", {"command": "python3 - <<'E'\nopen('failfirst.json','w').write('{}')\nE"}),
                  ("write_file", {"path": "failfirst.json", "content": "{}"}),
                  ("delete_file", {"file_path": ".failfirst.lock.json"})]
        for name, inp in denied:
            r = self.tool(d, name, inp)
            self.assertEqual(r.returncode, 2, (name, inp, r.stdout))
            out = json.loads(r.stdout.strip().splitlines()[-1])
            self.assertEqual(out["decision"], "deny")
            self.assertTrue(out["reason"])

    def test_allowed_calls(self):
        d = self.baselined()
        allowed = [("write", {"file_path": "calc.py", "content": FIXED}),
                   ("read_file", {"target_file": "failfirst.json"}),
                   ("run_terminal_command", {"command": "cat failfirst.json"}),
                   ("run_terminal_command", {"command": "failfirst verify failfirst.json"}),
                   ("run_terminal_command", {"command": "python3 -m pytest -q"})]
        for name, inp in allowed:
            r = self.tool(d, name, inp)
            self.assertEqual(r.returncode, 0, (name, inp, r.stdout))
            self.assertNotIn("deny", r.stdout)

    def test_other_workspace_and_bad_input_fail_open(self):
        self.baselined()
        other = self.toy()
        self.assertEqual(self.tool(other, "write", {"file_path": "failfirst.json"}).returncode, 0)
        self.assertEqual(self.ff(["hook", "pre-tool-use"], other, "not json").returncode, 0)


class StopTests(Base):
    def test_red_blocks_shutdown_and_green_pass(self):
        d = self.baselined()
        r = self.stop(d)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)["decision"], "block")
        self.assertIn("failfirst", r.stdout)
        self.assertEqual(self.stop(d, reason="shutdown").returncode, 0)
        (d / "calc.py").write_text(FIXED)
        self.assertEqual(self.stop(d).returncode, 0)

    def test_block_reason_names_the_failing_check(self):
        d = self.baselined()
        reason = json.loads(self.stop(d).stdout)["reason"]
        self.assertIn("add-works", reason)
        self.assertIn("from calc import add", reason)  # what the check runs

    def test_cap_on_consecutive_blocks(self):
        d = self.baselined()
        env = {**self.env, "FAILFIRST_GROK_MAX_STOP_BLOCKS": "2"}
        codes = [self.stop(d, sid="cap", env=env).returncode for _ in range(3)]
        self.assertEqual(codes, [2, 2, 0])

    def test_green_resets_counter(self):
        d = self.baselined()
        env = {**self.env, "FAILFIRST_GROK_MAX_STOP_BLOCKS": "1"}
        self.assertEqual(self.stop(d, env=env).returncode, 2)
        (d / "calc.py").write_text(FIXED)
        self.assertEqual(self.stop(d, env=env).returncode, 0)
        (d / "calc.py").write_text(BUGGY)
        self.assertEqual(self.stop(d, env=env).returncode, 2)

    def test_lock_tamper_and_weakened_criteria(self):
        d = self.baselined()
        (d / "calc.py").write_text(FIXED)
        lock = d / ".failfirst.lock.json"
        orig = lock.read_bytes()
        lock.write_bytes(orig + b"\n")
        r = self.stop(d, sid="t1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("lockfile", r.stdout)
        lock.write_bytes(orig)
        self.assertEqual(self.stop(d, sid="t2").returncode, 0)
        weak = json.loads(json.dumps(CRIT))
        weak["criteria"][0]["check"]["cmd"] = "true"
        (d / "failfirst.json").write_text(json.dumps(weak))
        self.assertEqual(self.stop(d, sid="t3").returncode, 2)


class RunTests(Base):
    def fake_grok(self, fix_on: int):
        t = Path(tempfile.mkdtemp(prefix="ffg_fake_"))
        self.addCleanup(shutil.rmtree, t, True)
        count = t / "count"
        script = t / "grok"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "n=$(( $(cat %s 2>/dev/null || echo 0) + 1 )); echo $n > %s\n"
            "echo \"$@\" >> %s.args\n"
            "if [ $n -ge %d ]; then printf 'def add(a, b):\\n    return a + b\\n' > calc.py; fi\n"
            % (count, count, count, fix_on))
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return str(script), count

    def run_with(self, d, fix_on, extra=()):
        bin_, count = self.fake_grok(fix_on)
        env = {**self.env, "FAILFIRST_GROK_BIN": bin_}
        r = self.ff(["run"] + list(extra) + ["--", "Fix add"], d, env=env)
        return r, count

    def test_retries_until_green(self):
        d = self.baselined()
        r, count = self.run_with(d, 2, ["--max-rounds", "3"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(count.read_text().strip(), "2")
        args = Path(str(count) + ".args").read_text()
        self.assertEqual(args.count("--always-approve"), 2)
        self.assertEqual(args.count("--output-format plain -c"), 1)  # the flag, not prompt text
        self.assertIn("not proven", args)

    def test_stops_red_after_max_rounds(self):
        d = self.baselined()
        r, count = self.run_with(d, 99, ["--max-rounds", "3"])
        self.assertEqual(r.returncode, 1)
        self.assertEqual(count.read_text().strip(), "3")

    def test_task_starting_with_dash_stays_one_argument(self):
        d = self.baselined()
        bin_, count = self.fake_grok(1)
        env = {**self.env, "FAILFIRST_GROK_BIN": bin_}
        r = self.ff(["run", "--", "-x fix add"], d, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("--single=-x fix add", Path(str(count) + ".args").read_text())

    def test_requires_baseline(self):
        d = self.toy()
        r, _ = self.run_with(d, 1)
        self.assertEqual(r.returncode, 2)


class InstallTests(Base):
    def test_install_hooks_idempotent(self):
        d = self.toy()
        for _ in range(2):
            r = self.ff(["install-hooks"], d)
            self.assertEqual(r.returncode, 0)
        path = Path(self.home) / "hooks" / "failfirst.json"
        self.assertEqual(r.stdout.strip(), str(path))
        hooks = json.loads(path.read_text())["hooks"]
        self.assertEqual(hooks["PreToolUse"][0]["hooks"][0]["timeout"], 15)
        self.assertEqual(hooks["Stop"][0]["hooks"][0]["timeout"], 600)
        self.assertIn("failfirst_grok.py", hooks["Stop"][0]["hooks"][0]["command"])
        self.assertIn("hook stop", hooks["Stop"][0]["hooks"][0]["command"])

    def test_status_exit_codes(self):
        d = self.baselined()
        self.assertEqual(self.ff(["status"], d).returncode, 1)
        (d / "calc.py").write_text(FIXED)
        self.assertEqual(self.ff(["status"], d).returncode, 0)


if __name__ == "__main__":
    unittest.main()
