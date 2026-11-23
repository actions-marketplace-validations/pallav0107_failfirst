"""Known-answer fixtures for the metric, the cluster bootstrap and the decision rule."""
import copy
import math

import pytest

import analyze as A
import common as C

P, F, E = C.PASS, C.FAIL, C.ERROR
LABELS = {"r1": "resolved", "r2": "resolved", "r3": "resolved",
          "u1": "unresolved", "u2": "unresolved", "u3": "unresolved"}
GOOD_AUDIT = {"n": 120, "agree": 120, "by_label": {"resolved": {"n": 60, "agree": 60},
                                                       "unresolved": {"n": 60, "agree": 60}}}


def chk(cid, unfixed, greens, strict=True, gold=P):
    """greens: set of patch ids the check passes on."""
    return {"check_id": cid, "unfixed": (unfixed, unfixed), "strict_fail": strict and unfixed == F,
            "patched": {p: (P if p in greens else F, True) for p in LABELS}, "gold": gold}


def inst(i, checks, repo="fixture/r"):
    return {"instance_id": f"fx__{i}", "repo": repo, "labels": dict(LABELS), "checks": checks}


def run(insts, **kw):
    args = dict(audit=GOOD_AUDIT, n_skipped=0, n_walked=len(insts), returned_models=["m"],
                n_missing=0, resamples=2000, placebo_draws=200)
    args.update(kw)
    return A.analyse(insts, **args)


# ------------------------------------------------------------------ known answer (C11)

def test_known_answer_fixture():
    fx = A.known_answer_fixture()
    st = A.stats_from_sums(A.sum_vectors([A.instance_vector(i) for i in fx]))
    assert st["fgs_a"] == pytest.approx(1 / 3)       # greens: vac/right, vac/wrong, ff/right
    assert st["fgs_b"] == 0.0                        # greens: ff/right only
    assert st["delta"] == pytest.approx(1 / 3)
    assert st["vacuous_share"] == 0.5
    assert st["residual"] == 0.0                     # ff check rejects the wrong patch
    assert st["kept_share"] == 0.5                   # B keeps 1 of A's 2 greens on the right patch
    A.self_test()


def test_unapplied_patch_is_never_green():
    fx = A.known_answer_fixture()
    fx[0]["checks"][0]["patched"]["wrong"] = (P, False)
    st = A.stats_from_sums(A.sum_vectors([A.instance_vector(i) for i in fx]))
    assert st["fgs_a"] == 0.0


# ------------------------------------------------------------------ bootstrap

def test_bootstrap_identical_clusters_collapse_to_point():
    one = [chk("v", P, set(LABELS)), chk("f", F, {"r1", "r2", "r3"})]
    insts = [inst(i, copy.deepcopy(one)) for i in range(30)]
    vecs = [A.instance_vector(x) for x in insts]
    b = A.cluster_bootstrap(vecs, ("delta",), resamples=500)
    point = A.stats_from_sums(A.sum_vectors(vecs))["delta"]
    assert point == pytest.approx(1 / 3)             # A: 3 of 9 greens unresolved; B: 0 of 3
    assert b["delta"]["ci95"] == pytest.approx([point, point])


def test_bootstrap_two_cluster_types_known_bounds_and_reproducible():
    """Half the instances have D=1/3, half D=0; every resample's D lies in [0, 1/3] and the
    CI is strictly inside, contains the point, and is identical on a re-run (seeded)."""
    hi = [chk("v", P, set(LABELS)), chk("f", F, {"r1", "r2", "r3"})]
    lo = [chk("f", F, set(LABELS)), chk("f2", F, set(LABELS))]
    insts = [inst(i, copy.deepcopy(hi if i % 2 else lo)) for i in range(40)]
    vecs = [A.instance_vector(x) for x in insts]
    b1 = A.cluster_bootstrap(vecs, ("delta",), resamples=2000)
    b2 = A.cluster_bootstrap(vecs, ("delta",), resamples=2000)
    point = A.stats_from_sums(A.sum_vectors(vecs))["delta"]
    lo_ci, hi_ci = b1["delta"]["ci95"]
    assert b1 == b2
    assert 0 < lo_ci <= point <= hi_ci < 1 / 3
    assert hi_ci - lo_ci > 0.02                       # it really resamples


def test_percentile_matches_numpy_linear():
    np = pytest.importorskip("numpy")
    vals = sorted([0.3, 0.1, 0.7, 0.2, 0.9, 0.5, 0.05])
    for q in (2.5, 50, 97.5):
        assert A.percentile(vals, q) == pytest.approx(float(np.percentile(vals, q)))


def test_bootstrap_cluster_unit_is_instance():
    """Resampling is by instance: duplicating every check inside each instance must not
    narrow the CI (a pair-level bootstrap would)."""
    import random
    rng = random.Random(3)
    base = []
    for i in range(40):
        g = set(p for p in LABELS if rng.random() < 0.5)
        base.append(inst(i, [chk("v", P, set(LABELS)), chk("f", F, g)]))
    doubled = [dict(x, checks=x["checks"] * 3) for x in base]
    w = lambda insts: (lambda c: c[1] - c[0])(A.cluster_bootstrap([A.instance_vector(x) for x in insts],
                                                                  ("delta",), resamples=2000)["delta"]["ci95"])
    assert w(base) > 0.05
    assert w(doubled) == pytest.approx(w(base), rel=0.25)


# ------------------------------------------------------------------ decision rule

def test_supported_fixture():
    """Many vacuous checks that pass everything; fail-first checks pass only resolved."""
    insts = [inst(i, [chk("v", P, set(LABELS)), chk("f1", F, {"r1", "r2", "r3"}),
                      chk("f2", F, {"r1", "r2", "u1"} if i % 4 == 0 else {"r1", "r2", "r3"})])
             for i in range(100)]
    out = run(insts)
    assert out["primary"]["delta_fgs"] >= 0.10
    assert out["primary"]["ci95"][0] > 0
    assert out["primary"]["delta_fgs"] > out["placebo"]["p975"]
    assert out["verdict"] == "SUPPORTED"


def test_against_fixture_no_vacuous_checks_filter_buys_nothing():
    """Thesis should be judged AGAINST: no check passes the unfixed tree, and the fail-first
    checks wave unresolved patches through as often as everything else."""
    insts = [inst(i, [chk("f1", F, {"r1", "r2", "u1"}), chk("f2", F, {"r1", "u2"}),
                      chk("e", E, set())]) for i in range(100)]
    out = run(insts)
    assert out["primary"]["delta_fgs"] == pytest.approx(0.0)
    assert out["primary"]["ci95"][1] < 0.10
    assert out["secondary"]["vacuous_share"] == 0.0
    assert out["verdict"] == "AGAINST"


def test_against_when_upper_bound_below_10pp_even_with_vacuous_checks():
    assert A.decide(0.05, [0.01, 0.09], 0.0, s1_ci_hi=0.3, integrity=[]) == "AGAINST"
    assert A.decide(0.05, [0.01, 0.10], 0.0, s1_ci_hi=0.3, integrity=[]) == "INCONCLUSIVE"


def test_against_when_vacuous_share_upper_bound_below_5pct():
    assert A.decide(0.2, [0.12, 0.3], 0.05, s1_ci_hi=0.04, integrity=[]) == "AGAINST"


def test_inconclusive_when_ci_straddles():
    assert A.decide(0.12, [-0.01, 0.25], 0.0, s1_ci_hi=0.3, integrity=[]) == "INCONCLUSIVE"
    assert A.decide(0.08, [0.02, 0.15], 0.0, s1_ci_hi=0.3, integrity=[]) == "INCONCLUSIVE"


def test_supported_needs_delta_above_placebo_null_97_5th_percentile():
    assert A.decide(0.2, [0.1, 0.3], 0.05, 0.3, []) == "SUPPORTED"
    assert A.decide(0.2, [0.1, 0.3], 0.2, 0.3, []) == "INCONCLUSIVE"      # not strictly above
    assert A.decide(0.2, [0.1, 0.3], float("nan"), 0.3, []) == "INCONCLUSIVE"


def test_against_when_filter_harms_precision():
    assert A.decide(-0.2, [-0.3, -0.1], 0.0, 0.3, []) == "AGAINST"


@pytest.mark.parametrize("kw,needle", [
    ({"audit": {"n": 120, "agree": 116, "by_label": {"resolved": {"n": 60, "agree": 60},
                                                     "unresolved": {"n": 60, "agree": 56}}}}, "unresolved"),
    ({"audit": {"n": 120, "agree": 120}}, "per-label"),
    ({"audit": None}, "audit missing"),
    ({"n_skipped": 30, "n_walked": 130}, "skipped"),
    ({"returned_models": ["a", "b"]}, "distinct model"),
    ({"returned_models": []}, "distinct model"),
    ({"n_missing": 1}, "missing"),
])
def test_integrity_stop_is_blocked(kw, needle):
    insts = [inst(i, [chk("v", P, set(LABELS)), chk("f", F, {"r1"})]) for i in range(20)]
    out = run(insts, **kw)
    assert out["verdict"] == "BLOCKED"
    assert any(needle in s for s in out["integrity_failures"])


def test_skip_share_boundary_is_inclusive_20pct():
    assert not A.integrity_failures(audit=GOOD_AUDIT, n_skipped=20, n_walked=100,
                                    returned_models=["m"], n_missing=0)
    assert A.integrity_failures(audit=GOOD_AUDIT, n_skipped=21, n_walked=100,
                                returned_models=["m"], n_missing=0)


def test_undefined_fgs_b_is_inconclusive_not_supported():
    insts = [inst(i, [chk("v", P, set(LABELS)), chk("f", F, set())]) for i in range(20)]
    out = run(insts)
    assert math.isnan(out["arms"]["failfirst"]["fgs"])
    assert out["verdict"] == "INCONCLUSIVE"


def test_strict_rule_drops_non_assertion_failures():
    insts = [inst(i, [chk("v", P, set(LABELS)), chk("f", F, {"r1", "u1"}, strict=False),
                      chk("g", F, {"r1", "r2"}, strict=True)]) for i in range(10)]
    out = run(insts)
    assert out["arms"]["failfirst"]["n_checks"] == 20
    assert out["secondary"]["strict_delta_fgs"] > out["primary"]["delta_fgs"]
