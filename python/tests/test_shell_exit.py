"""Shell exit 127/126 (command not found / not executable) is an error, not a failure."""
from failfirst import normalize_criteria
from failfirst.runner import evaluate


def _eval(check, code):
    crit = normalize_criteria([{"id": "A", "statement": "s", "check": dict({"type": "command"}, **check)}])[0]
    return evaluate(crit, {"exit": code, "output": ""})


def test_shell_127_is_error():
    r = _eval({"cmd": "nope"}, 127)
    assert r["status"] == "error"
    assert "could not find" in r["detail"] and "127" in r["detail"]


def test_shell_126_is_error():
    r = _eval({"cmd": "nope"}, 126)
    assert r["status"] == "error"
    assert "could not execute" in r["detail"] and "126" in r["detail"]


def test_shell_127_with_expect_exit_127_passes():
    assert _eval({"cmd": "x", "expect_exit": 127}, 127)["status"] == "passed"


def test_shell_126_with_expect_exit_127_is_error():
    assert _eval({"cmd": "x", "expect_exit": 127}, 126)["status"] == "error"


def test_argv_127_is_failed():
    assert _eval({"argv": ["x"]}, 127)["status"] == "failed"


def test_other_exit_unchanged():
    assert _eval({"cmd": "x"}, 1)["status"] == "failed"
