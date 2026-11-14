import glob
import json
import os

import pytest

from failfirst import baseline, criterion_hash, normalize_criteria, verify
from failfirst.runner import evaluate

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "conformance")
FILES = sorted(glob.glob(os.path.join(ROOT, "*.json")))


def _vectors():
    for f in FILES:
        for v in json.load(open(f, encoding="utf-8"))["vectors"]:
            yield pytest.param(v, id=f"{os.path.basename(f)}::{v['name']}")


def test_vectors_present():
    assert FILES, "conformance vectors not found"


@pytest.mark.parametrize("vec", list(_vectors()))
def test_vector(vec, tmp_path):
    lock = str(tmp_path / "lock.json")
    if "hash" in vec:
        crit = normalize_criteria([vec["criterion"]])[0]
        assert criterion_hash(crit) == vec["hash"]
        return
    crit = normalize_criteria(vec["criteria"])
    by_id = {c["id"]: c for c in crit}
    if "evaluate" in vec:
        for case in vec["evaluate"]:
            got = evaluate(by_id[case["id"]], case["observation"])["status"]
            assert got == case["status"], case
        return
    obs_b = vec["baseline_observations"]
    rep, code = baseline(crit, lock, observe=lambda c: obs_b[c["id"]])
    assert code == vec["expected"]["baseline_exit_code"]
    verify_criteria = normalize_criteria(vec.get("verify_criteria", vec["criteria"]))
    obs_v = vec["verify_observations"]
    rep, code = verify(verify_criteria, lock, observe=lambda c: obs_v[c["id"]])
    exp = vec["expected"]
    assert {r["id"]: r["verdict"] for r in rep["criteria"]} == exp["verdicts"]
    assert rep["status"] == exp["status"]
    assert code == exp["exit_code"]
