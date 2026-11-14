import json
import sys

import pytest

from failfirst import SpecError, load_criteria
from failfirst.cli import main

PY = json.dumps(sys.executable)


def write(tmp_path, body):
    (tmp_path / "failfirst.json").write_text(json.dumps(body))
    return str(tmp_path / "failfirst.json")


def crit(tmp_path):
    return write(tmp_path, {"criteria": [
        {"id": "A", "statement": "flag exists",
         "check": {"cmd": f"{PY} -c \"import os,sys; sys.exit(0 if os.path.exists('flag') else 1)\""}},
        {"id": "J", "statement": "reads well", "judgment": True}]})


def test_full_flow_with_real_commands(tmp_path, capsys):
    path = crit(tmp_path)
    assert main(["baseline", path]) == 0
    assert main(["verify", path]) == 1          # not fixed yet
    (tmp_path / "flag").write_text("x")
    assert main(["verify", path, "--json"]) == 3  # proven, judgment pending
    out = capsys.readouterr().out
    assert json.loads(out[out.index("{"):])["status"] == "awaiting_review"


def test_edit_after_baseline_invalidates(tmp_path):
    path = crit(tmp_path)
    main(["baseline", path])
    (tmp_path / "flag").write_text("x")
    doc = json.load(open(path))
    doc["criteria"][0]["check"]["cmd"] = f"{PY} -c pass"
    json.dump(doc, open(path, "w"))
    assert main(["verify", path]) == 1


def test_vacuous_baseline(tmp_path):
    (tmp_path / "flag").write_text("x")
    path = crit(tmp_path)
    assert main(["baseline", path]) == 1
    assert main(["verify", path]) == 1


def test_refuses_overwrite_and_missing_lock(tmp_path):
    path = crit(tmp_path)
    assert main(["verify", path]) == 2
    main(["baseline", path])
    assert main(["baseline", path]) == 2
    assert main(["baseline", path, "--force"]) == 0


def test_yaml_loads_and_equals_json(tmp_path):
    y = tmp_path / "c.yaml"
    y.write_text("criteria:\n  - id: A\n    check: {cmd: 'true'}\n")
    j = tmp_path / "c.json"
    j.write_text(json.dumps({"criteria": [{"id": "A", "check": {"cmd": "true"}}]}))
    assert load_criteria(str(y)) == load_criteria(str(j))


@pytest.mark.parametrize("bad", [
    {"criteria": []},
    {"criteria": [{"id": "A", "check": {"cmd": "x"}}, {"id": "A", "check": {"cmd": "x"}}]},
    {"criteria": [{"id": "A", "check": {"cmd": "x", "expect_exti": 1}}]},
    {"criteria": [{"id": "A", "judgment": True, "check": {"cmd": "x"}}]},
    {"criteria": [{"id": "A"}]},
    {"criteria": [{"id": "A", "check": {"cmd": "x", "argv": ["x"]}}]},
])
def test_invalid_specs_rejected(tmp_path, bad):
    with pytest.raises(SpecError):
        load_criteria(write(tmp_path, bad))


def test_timeout_is_error_not_failure(tmp_path):
    path = write(tmp_path, {"criteria": [{"id": "A", "check": {"argv": [sys.executable, "-c", "import time; time.sleep(5)"], "timeout": 1}}]})
    assert main(["baseline", path, "--json"]) == 1
    lock = json.load(open(tmp_path / ".failfirst.lock.json"))
    assert lock["criteria"]["A"]["baseline"]["status"] == "error"
