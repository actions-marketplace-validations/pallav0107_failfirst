"""Regression tests for the independent methodology review (items 1-9 and the plausible items).
Each was written to FAIL on the pre-review code."""
import hashlib
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import analyze as A
import audit_oracle as AO
import box_runner as BR
import common as C
import fetch_patches as F
import generate as G
import sample as S

EXP = Path(__file__).resolve().parent.parent
PILOT_ID = C.read_lines(EXP / "pilot_ids.txt")[0]


# ====================================================================== item 1: freeze covers all

def _frozen_copy(tmp_path):
    dst = tmp_path / "exp"
    shutil.copytree(EXP, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "PREREG.sha256"))
    import freeze
    freeze.write_manifest(dst)
    return dst


def _run(dst, *args):
    p = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=str(dst.parent),
                       env={k: v for k, v in __import__("os").environ.items() if k != "FFX_ENV_FILE"})
    return p.returncode, p.stdout + p.stderr


def test_freeze_manifest_covers_every_file(tmp_path):
    dst = _frozen_copy(tmp_path)
    (dst / "__pycache__").mkdir(exist_ok=True)
    (dst / "__pycache__" / "x.pyc").write_bytes(b"x")
    names = {ln.split("  ", 1)[1] for ln in (dst / "PREREG.sha256").read_text().splitlines()}
    for must in ("PREREG.md", "prompt.txt", "sample.lock.json", "verified_ids.txt", "pilot_ids.txt",
                 ".gitattributes", "analyze.py", "generate.py", "box/box_runner.py", "box/pull_images.sh",
                 "tests/test_ffx_review_fixes.py"):
        assert must in names, must
    assert not any("__pycache__" in n for n in names) and "PREREG.sha256" not in names
    ok, msg = C.prereg_gate(dst)[:2]
    assert ok, msg


@pytest.mark.parametrize("victim", ["common.py", "sample.lock.json", "box/box_runner.py", ".gitattributes"])
def test_gate_refuses_any_tampered_file(tmp_path, victim):
    dst = _frozen_copy(tmp_path)
    with (dst / victim).open("ab") as fh:
        fh.write(b"\n#tamper\n")
    rc, out = _run(dst, dst / "analyze.py", "--dry-run")
    assert "BLOCKED: prereg hash" in out and rc != 0


def test_gate_refuses_an_unfrozen_extra_file(tmp_path):
    dst = _frozen_copy(tmp_path)
    (dst / "sneaky.py").write_text("x = 1\n")
    rc, out = _run(dst, dst / "analyze.py", "--dry-run")
    assert "BLOCKED: prereg hash" in out and rc != 0


def test_frozen_mismatch_refuses_even_pilot_generation(tmp_path):
    dst = _frozen_copy(tmp_path)
    with (dst / "generate.py").open("a") as fh:
        fh.write("\n# tamper\n")
    rc, out = _run(dst, dst / "generate.py", "--pilot", PILOT_ID, "--run-dir", tmp_path / "r")
    assert rc == 3 and "BLOCKED: prereg hash" in out


@pytest.mark.parametrize("script,args", [
    ("generate.py", ["--lock", "{lock}", "--run-dir", "{tmp}/r"]),
    ("run_checks.py", ["bundle", "--run-dir", "{tmp}/r", "--lock", "{lock}"]),
    ("audit_oracle.py", ["prepare", "--run-dir", "{tmp}/r", "--lock", "{lock}"]),
])
def test_tools_refuse_a_lock_that_is_not_the_frozen_one(tmp_path, script, args):
    dst = _frozen_copy(tmp_path)
    other = tmp_path / "other_lock.json"
    other.write_bytes((dst / "sample.lock.json").read_bytes() + b" ")
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "run_manifest.json").write_text("{}")
    argv = [a.format(lock=other, tmp=tmp_path) for a in args]
    rc, out = _run(dst, dst / script, *argv)
    assert rc == 3 and "BLOCKED: lock" in out, out


# ====================================================================== item 2: infra = MISSING

def test_missing_exit_code_is_missing_not_error():
    assert C.classify_run(None) == C.MISSING


@pytest.mark.parametrize("row,completed", [
    ({"exit_code": 1, "docker_rc": 0, "patch_sha256": None, "applied": None}, True),
    ({"exit_code": 124, "docker_rc": 0, "patch_sha256": None, "applied": None}, True),   # timeout is real
    ({"exit_code": None, "docker_rc": 0, "patch_sha256": None, "applied": None}, False),
    ({"exit_code": 0, "docker_rc": 125, "patch_sha256": None, "applied": None}, False),  # docker error
    ({"exit_code": None, "docker_rc": 0, "patch_sha256": "p", "applied": False}, False),  # apply failed
    ({"exit_code": 0, "docker_rc": 0, "patch_sha256": "p", "applied": True}, True),
    ({"exit_code": 0, "docker_rc": 0, "patch_sha256": None, "applied": None, "outer_timeout": True}, False),
])
def test_row_completed(row, completed):
    assert C.row_completed(row) is completed


def test_runner_retries_missing_rows_once():
    tasks = [{"check_id": "c", "target": t} for t in ("a", "b", "d")]
    rows = [{"check_id": "c", "target": "a", "attempt": 1, "status": "completed"},
            {"check_id": "c", "target": "b", "attempt": 1, "status": "missing"},
            {"check_id": "c", "target": "d", "attempt": 1, "status": "missing"},
            {"check_id": "c", "target": "d", "attempt": 2, "status": "missing"}]
    pend = BR.pending(tasks, rows, max_attempts=2)
    assert [(t["target"], a) for t, a in pend] == [("b", 2)]
    assert [(t["target"], a) for t, a in BR.pending(tasks, [], 2)] == [("a", 1), ("b", 1), ("d", 1)]
    assert isinstance(BR.loadavg(), (float, type(None)))


# ====================================================================== items 2+3: assemble

def _lock_manifest_rows():
    iid = "r__r-1"
    patches = [{"submission": f"s{j}", "label": "resolved" if j < 3 else "unresolved",
                "patch_sha256": f"p{j}"} for j in range(6)]
    lock = {"instances": [{"instance_id": iid, "repo": "r/r", "patches": patches}]}
    checks = [{"check_id": f"{iid}#{k}", "instance_id": iid, "k": k, "check_sha256": f"c{k}"} for k in (1, 2, 3)]
    rows = []
    for c in checks:
        base = {"check_id": c["check_id"], "check_sha256": c["check_sha256"], "attempt": 1,
                "docker_rc": 0, "timed_out": False, "status": "completed"}
        rows += [dict(base, target=t, exit_code=1, patch_sha256=None, applied=None) for t in ("unfixed1", "unfixed2")]
        rows += [dict(base, target="patch:" + p["submission"], exit_code=0, patch_sha256=p["patch_sha256"],
                      applied=True) for p in patches]
        rows.append(dict(base, target="gold", exit_code=0, patch_sha256="g", applied=True))
    return lock, {"checks": checks}, rows


def test_assemble_counts_exit_code_none_as_missing():
    lock, man, rows = _lock_manifest_rows()
    rows[3]["exit_code"] = None
    _, missing, _, _, problems = A.assemble(lock, man, rows)
    assert missing == 1


def test_assemble_unapplied_patch_row_is_missing():
    lock, man, rows = _lock_manifest_rows()
    rows[3]["applied"] = False
    assert A.assemble(lock, man, rows)[1] == 1


def test_assemble_uses_retry_attempt():
    lock, man, rows = _lock_manifest_rows()
    rows[3]["exit_code"] = None
    rows[3]["status"] = "missing"
    rows.append(dict(rows[3], attempt=2, exit_code=0, status="completed"))
    _, missing, pairs, _, problems = A.assemble(lock, man, rows)
    assert missing == 0 and not problems and pairs == 18


def test_assemble_blocks_duplicate_completed_rows():
    lock, man, rows = _lock_manifest_rows()
    rows.append(dict(rows[4], attempt=2))
    problems = A.assemble(lock, man, rows)[4]
    assert any("duplicate" in p for p in problems)


def test_assemble_blocks_attempt_beyond_registered_retry():
    lock, man, rows = _lock_manifest_rows()
    rows[4] = dict(rows[4], attempt=3)
    assert any("attempt" in p for p in A.assemble(lock, man, rows)[4])


# ====================================================================== item 3: generations

def _gen(k, attempt, usable, sha):
    return {"instance_id": "r__r-1", "k": k, "attempt": attempt, "ok": True, "usable": usable,
            "script_sha256": sha if usable else None, "returned_model": "m"}


def test_generation_crosscheck_regenerated_slot():
    man = {"checks": [{"check_id": "r__r-1#1", "instance_id": "r__r-1", "k": 1, "check_sha256": "S1",
                       "generation_failed": False}]}
    good = [_gen(1, 0, False, None), _gen(1, 1, True, "S1")]
    assert A.generation_problems(man, good) == []
    assert A.generation_problems(man, [_gen(1, 0, False, None), _gen(1, 1, True, "S0"), _gen(1, 2, True, "S1")])
    assert A.generation_problems(man, good + [_gen(1, 2, True, "S1")])           # reply after the usable one
    assert A.generation_problems(man, [_gen(1, a, False, None) for a in range(4)] + [_gen(1, 4, True, "S1")])
    stub = {"checks": [dict(man["checks"][0], check_sha256=C.sha256_bytes(G.STUB.encode()),
                            generation_failed=True)]}
    assert A.generation_problems(stub, [_gen(1, a, False, None) for a in range(3)]) == []


def test_generate_slot_logs_script_sha_of_every_usable_reply(tmp_path):
    replies = iter([{"ok": True, "text": "no (", "returned_model": "m"},
                    {"ok": True, "text": "```python\nx = 1\n```", "returned_model": "m"}])
    rows = []
    inst = {"instance_id": "r__r-1", "repo": "r", "version": "1", "problem_statement": "p"}
    c = G.generate_slot("K", "{{REPO}}", inst, 1, tmp_path, rows.append, lambda *a: next(replies))
    assert [r["script_sha256"] for r in rows] == [None, c["check_sha256"]]
    assert len(rows) <= 3


# ====================================================================== item 3+4: audit

def _lock_insts(n=100):
    return [{"instance_id": f"r__r-{i}", "patches": [{"submission": f"s{j}", "label": "resolved" if j < 3 else
                                                      "unresolved"} for j in range(6)]} for i in range(n)]


def test_audit_selection_is_stratified_60_60():
    pairs = AO.select_pairs(_lock_insts())
    assert len(pairs) == 120
    assert sum(p["label"] == "resolved" for p in pairs) == 60


def _audit_from(pairs, wrong_unres=0, wrong_res=0):
    rows, wu, wr = [], wrong_unres, wrong_res
    for p in pairs:
        agree = True
        if p["label"] == "unresolved" and wu:
            agree, wu = False, wu - 1
        elif p["label"] == "resolved" and wr:
            agree, wr = False, wr - 1
        rows.append(dict(p, agree=agree))
    return AO.summarise(rows)


def test_audit_must_match_seeded_selection_and_per_label_threshold():
    lock = {"instances": _lock_insts()}
    pairs = AO.select_pairs(lock["instances"])
    assert A.audit_problems(lock, _audit_from(pairs)) == []
    swapped = [dict(p) for p in pairs]
    swapped[0]["submission"] = "s5" if swapped[0]["submission"] != "s5" else "s4"
    assert A.audit_problems(lock, _audit_from(swapped))                 # pair set differs
    assert A.audit_problems(lock, _audit_from(pairs[:100]))             # wrong n
    a = _audit_from(pairs, wrong_unres=4)                               # 116/120 overall, 56/60 unresolved
    assert a["agree"] >= 0.95 * a["n"]
    assert any("unresolved" in p for p in A.audit_problems(lock, a))


def test_audit_collect_uses_one_run_id(tmp_path):
    pairs = [{"instance_id": "a__a-1", "submission": "s1", "label": "resolved"}]
    d = tmp_path / "other_run" / (AO.MODEL_PREFIX + "s1") / "a__a-1"
    d.mkdir(parents=True)
    (d / "report.json").write_text(json.dumps({"a__a-1": {"resolved": True}}))
    out = AO.collect(pairs, tmp_path, run_id=AO.RUN_ID)
    assert out["agree"] == 0 and out["missing"] == 1


# ====================================================================== item 4: unresolved evidence

REP_OK = {"x__x-1": {"patch_successfully_applied": True, "resolved": False,
                     "tests_status": {"FAIL_TO_PASS": {"success": [], "failure": ["t1"]},
                                      "PASS_TO_PASS": {"success": ["t2"], "failure": []}}}}


@pytest.mark.parametrize("mutate,ok", [
    (lambda r: r, True),
    (lambda r: None, False),
    (lambda r: {"x__x-1": dict(r["x__x-1"], patch_successfully_applied=False)}, False),
    (lambda r: {"x__x-1": {k: v for k, v in r["x__x-1"].items() if k != "tests_status"}}, False),
    (lambda r: {"x__x-1": dict(r["x__x-1"], tests_status={"FAIL_TO_PASS": {"success": [], "failure": ["t1"]},
                                                          "PASS_TO_PASS": {"success": [], "failure": ["t2"]}})},
     False),
    (lambda r: {"x__x-1": dict(r["x__x-1"], tests_status={"FAIL_TO_PASS": {"success": [], "failure": []},
                                                          "PASS_TO_PASS": {"success": ["t2"], "failure": []}})},
     False),
])
def test_unresolved_report_evidence(mutate, ok):
    import copy
    assert F.unresolved_report_ok(mutate(copy.deepcopy(REP_OK)), "x__x-1") is ok


def test_selection_rejects_unresolved_without_evidence_and_logs_label_conflicts():
    subs = [f"sub{i:02d}" for i in range(14)]
    pool = {s: {"resolved": ["x__x-1"] if i % 2 else [], "unresolved": [] if i % 2 else ["x__x-1"],
                "logs": "https://example.invalid", "results_sha256": "0"} for i, s in enumerate(subs)}
    order = F.candidate_order(pool, "x__x-1")
    patches = {s: f"diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+v_{s} = 1\n" for s in pool}
    first_res = next(s for s, lab in order if lab == "resolved")
    conflict = next(s for s, lab in order if lab == "unresolved")
    patches[conflict] = patches[first_res]                       # same edit, opposite label
    bad_report = [s for s, lab in order if lab == "unresolved" and s != conflict][0]
    res = F.select_patches(pool, {"instance_id": "x__x-1", "repo": "r", "base_commit": "c"},
                           fetch=lambda s, i: patches[s], apply_ok=lambda p: (True, ""),
                           report_ok=lambda s, i: s != bad_report)
    by = {t["submission"]: t["result"] for t in res["tried"]}
    assert by[bad_report] == "no_report_evidence"
    if order.index((conflict, "unresolved")) > order.index((first_res, "resolved")):
        assert by[conflict] == "label_conflict"
    assert res["complete"]


# ====================================================================== item 5: placebo

def test_placebo_is_stratified_by_instance_and_is_a_null_threshold():
    P, Fl = C.PASS, C.FAIL
    lab = {"r": "resolved", "u": "unresolved"}
    def chk(u, greens):
        return {"check_id": "c", "unfixed": (u, u), "strict_fail": False,
                "patched": {p: (P if p in greens else Fl, True) for p in lab}, "gold": P}
    # every instance keeps all or none of its checks in arm B -> stratified placebo == arm B exactly
    insts = [{"instance_id": f"i{i}", "repo": "r", "labels": lab,
              "checks": [chk(Fl, {"r"}), chk(Fl, {"r", "u"})] if i % 2 else [chk(P, {"r", "u"}), chk(P, {"u"})]}
             for i in range(20)]
    vecs = [A.instance_vector(x) for x in insts]
    plc = A.placebo(insts, vecs, draws=200)
    d = A.stats_from_sums(A.sum_vectors(vecs))["delta"]
    assert plc["p975"] == pytest.approx(d) and plc["delta_mean"] == pytest.approx(d)
    assert A.decide(d, [d - 0.01, d + 0.01], plc["p975"], 0.5, []) != "SUPPORTED"
    assert A.decide(0.2, [0.1, 0.3], 0.05, 0.5, []) == "SUPPORTED"
    assert A.decide(0.2, [0.1, 0.3], 0.25, 0.5, []) == "INCONCLUSIVE"


# ====================================================================== plausible: FPR/TPR, decomposition

def test_fpr_tpr_and_decomposition_known_answer():
    out = A.analyse(A.known_answer_fixture(), audit=None, n_skipped=0, n_walked=1, returned_models=["m"],
                    n_missing=0, resamples=50, placebo_draws=20)
    s = out["secondary"]
    assert s["fpr"] == {"unfiltered": 0.5, "failfirst": 0.0}
    assert s["tpr"] == {"unfiltered": 1.0, "failfirst": 1.0}
    dec = s["decomposition"]
    assert dec["from_removing_pass_on_unfixed"] + dec["from_removing_error_on_unfixed"] == pytest.approx(
        out["primary"]["delta_fgs"])
    assert dec["from_removing_pass_on_unfixed"] == pytest.approx(1 / 3)


# ====================================================================== plausible: strict assertion

def test_strict_assertion_needs_check_frame_and_final_assertion():
    own = ('Traceback (most recent call last):\n  File "/ffx/check.py", line 9, in <module>\n'
           '    assert x == 1\nAssertionError\n')
    lib_only = ('Traceback (most recent call last):\n  File "/testbed/lib.py", line 3, in f\n'
                'AssertionError: internal\n')
    printed = "expected AssertionError but got ValueError\n"
    chained = own + "\nDuring handling of the above exception, another exception occurred:\n\n" + \
        'Traceback (most recent call last):\n  File "/ffx/check.py", line 12, in <module>\nValueError: x\n'
    assert BR.strict_assertion(own)
    assert not BR.strict_assertion(lib_only)
    assert not BR.strict_assertion(printed)
    assert not BR.strict_assertion(chained)


# ====================================================================== item 7: pilot rule

def test_pilot_rule_is_deterministic():
    rows, checks = [], []
    for k in range(10):
        cid = f"p__p-1#{k}"
        checks.append({"check_id": cid, "instance_id": "p__p-1", "k": k, "check_sha256": "s"})
        crash = k < 7
        for t in ("unfixed1", "unfixed2", "gold"):
            rows.append({"check_id": cid, "target": t, "check_sha256": "s", "attempt": 1, "docker_rc": 0,
                         "exit_code": 1, "applied": True if t == "gold" else None,
                         "patch_sha256": "g" if t == "gold" else None,
                         "exc_type": "ImportError" if crash else "AssertionError"})
    rep = A.pilot_report({"checks": checks}, rows)
    assert rep["broken_share"] == pytest.approx(0.7) and rep["add_bm25"] is True
    rep = A.pilot_report({"checks": checks[7:]}, rows)
    assert rep["broken_share"] == 0.0 and rep["add_bm25"] is False


# ====================================================================== item 8: deep verify

def test_deep_verify_refetches_into_an_empty_cache(monkeypatch):
    seen = []
    walk = [{"instance_id": "x__x-1", "status": "included", "reason": None,
             "tried": [{"submission": "s", "label": "resolved", "result": "accepted"}]}]
    lock = {"walk": walk, "image_failures": {}, "instances": [{"instance_id": "x__x-1", "patches": ["P"]}],
            "labels": {"pool": {"s": "h"}}}

    def fake_pool(work):
        seen.append(("pool", work, list(Path(work).iterdir())))
        return {"s": {"results_sha256": "h"}}

    def fake_select(pool, inst, work, seed):
        seen.append(("select", work))
        return {"complete": True, "reason": None, "patches": ["P"], "tried": walk[0]["tried"]}
    ds = {"x__x-1": {"instance_id": "x__x-1"}}
    S.deep_check(lock, C.SEED, ds, pool_fetch=fake_pool, selector=fake_select)
    assert seen[0][0] == "pool" and seen[0][2] == [] and Path(seen[0][1]) != C.WORK_DIR
    assert seen[1][1] == seen[0][1]

    def lying_select(pool, inst, work, seed):
        return {"complete": True, "reason": None, "patches": ["P"],
                "tried": [{"submission": "s", "label": "resolved", "result": "no_apply"}]}
    with pytest.raises(S.VerifyError):
        S.deep_check(lock, C.SEED, ds, pool_fetch=fake_pool, selector=lying_select)


# ====================================================================== item 9: key path from env only

def test_key_file_only_from_environment(tmp_path, monkeypatch):
    assert not hasattr(G, "DEFAULT_ENV_FILE")
    src = (EXP / "generate.py").read_text(encoding="utf-8")
    assert "Path.home()" not in src and "harness" not in src.lower()      # no default key path
    for n in G.KEY_NAMES:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.delenv("FFX_ENV_FILE", raising=False)
    assert G.env_file_path() is None
    monkeypatch.setenv("FFX_ENV_FILE", str(tmp_path / ".env"))
    assert G.env_file_path() == tmp_path / ".env"


# ====================================================================== re-audit: label-conflict groups

def _conflict_pool(n=16):
    subs = [f"sub{i:02d}" for i in range(n)]
    return {s: {"resolved": ["x__x-1"] if i % 2 else [], "unresolved": [] if i % 2 else ["x__x-1"],
                "logs": "https://example.invalid", "results_sha256": "0"} for i, s in enumerate(subs)}


def _patch(tag):
    return f"diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+v_{tag} = 1\n"


def test_every_member_of_a_label_conflicting_group_is_ineligible():
    """The twin of an accepted patch may sit AFTER the point where the walk would stop; the
    accepted member must still be rejected, and so must its twin."""
    pool = _conflict_pool()
    order = F.candidate_order(pool, "x__x-1")
    patches = {s: _patch(s) for s in pool}
    first_sub, first_label = order[0]
    last_opposite = [s for s, lab in order if lab != first_label][-1]   # never reached by a plain walk
    patches[last_opposite] = patches[first_sub]
    res = F.select_patches(pool, {"instance_id": "x__x-1", "repo": "r", "base_commit": "c"},
                           fetch=lambda s, i: patches[s], apply_ok=lambda p: (True, ""),
                           report_ok=lambda s, i: True)
    by = {t["submission"]: t["result"] for t in res["tried"]}
    assert by[first_sub] == "label_conflict"
    assert first_sub not in {p["submission"] for p in res["patches"]}
    assert last_opposite not in {p["submission"] for p in res["patches"]}
    assert res["complete"]
    assert res["label_conflict_groups"] and {m["submission"] for m in res["label_conflict_groups"][0]["members"]} \
        == {first_sub, last_opposite}


def test_same_label_twins_are_not_a_conflict():
    pool = _conflict_pool()
    order = F.candidate_order(pool, "x__x-1")
    patches = {s: _patch(s) for s in pool}
    first_sub, first_label = order[0]
    twin = [s for s, lab in order if lab == first_label][-1]
    patches[twin] = patches[first_sub]
    res = F.select_patches(pool, {"instance_id": "x__x-1", "repo": "r", "base_commit": "c"},
                           fetch=lambda s, i: patches[s], apply_ok=lambda p: (True, ""),
                           report_ok=lambda s, i: True)
    assert {t["submission"]: t["result"] for t in res["tried"]}[first_sub] == "accepted"
    assert res["label_conflict_groups"] == []
