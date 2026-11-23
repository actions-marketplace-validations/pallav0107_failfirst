"""Exit-code classifier and the arm-B filter (known answers)."""
import itertools
import random

import pytest

import analyze as A
import common as C


@pytest.mark.parametrize("rc,timed_out,want", [
    (0, False, C.PASS),
    (1, False, C.FAIL),
    (2, False, C.FAIL),
    (126, False, C.ERROR),     # not executable
    (127, False, C.ERROR),     # command not found / stub for an unusable reply
    (124, False, C.ERROR),     # `timeout` stopped it
    (137, False, C.ERROR),     # `timeout -k` had to SIGKILL it
    (0, True, C.ERROR),        # outer timeout wins even if a 0 was seen
    (None, False, C.MISSING),  # container never reported: infrastructure, not an outcome
])
def test_classify_run(rc, timed_out, want):
    assert C.classify_run(rc, timed_out) == want


@pytest.mark.parametrize("a,b,want", [
    (C.PASS, C.PASS, C.PASS),
    (C.FAIL, C.FAIL, C.FAIL),
    (C.PASS, C.FAIL, C.ERROR),   # flaky
    (C.FAIL, C.PASS, C.ERROR),   # flaky
    (C.ERROR, C.FAIL, C.ERROR),
    (C.PASS, C.ERROR, C.ERROR),
])
def test_combine_unfixed_flaky_is_error(a, b, want):
    assert C.combine_unfixed(a, b) == want


def test_green_requires_pass_and_apply():
    assert C.is_green(C.PASS, True)
    assert not C.is_green(C.PASS, False)
    assert not C.is_green(C.FAIL, True)
    assert not C.is_green(C.ERROR, True)


def _rand_check(rng, unfixed):
    return {"check_id": "c", "unfixed": unfixed, "strict_fail": rng.random() < 0.5,
            "patched": {p: (rng.choice([C.PASS, C.FAIL, C.ERROR]), rng.random() < 0.9)
                        for p in ("p1", "p2", "p3", "p4")},
            "gold": rng.choice([C.PASS, C.FAIL])}


def test_arm_b_is_pure_function_of_unfixed_outcome():
    """Arm-B membership must not move when labels, patch outcomes, apply status, gold
    outcome or the strict flag are re-randomised with the unfixed runs held fixed."""
    rng = random.Random(7)
    outcomes = [C.PASS, C.FAIL, C.ERROR]
    for unfixed in itertools.product(outcomes, outcomes):
        memberships = set()
        for _ in range(50):
            inst = {"labels": {p: rng.choice(["resolved", "unresolved"]) for p in ("p1", "p2", "p3", "p4")},
                    "checks": [_rand_check(rng, unfixed)]}
            memberships.add(len(A.arm_checks(inst, "B")))
        assert len(memberships) == 1, unfixed
        want = 1 if unfixed == (C.FAIL, C.FAIL) else 0
        assert memberships == {want}, unfixed


def test_arm_b_follows_exit_codes_end_to_end():
    """From raw exit codes: only (non-zero, non-error) twice puts a check in arm B."""
    cases = {(1, 1): True, (0, 0): False, (1, 0): False, (127, 127): False,
             (126, 1): False, (2, 1): True}
    for (r1, r2), want in cases.items():
        u = C.combine_unfixed(C.classify_run(r1), C.classify_run(r2))
        assert C.in_failfirst_arm(u) is want, (r1, r2)


def test_arm_b_is_subset_of_arm_a():
    rng = random.Random(11)
    for _ in range(200):
        inst = {"labels": {p: "resolved" for p in ("p1", "p2", "p3", "p4")},
                "checks": [_rand_check(rng, (rng.choice([C.PASS, C.FAIL, C.ERROR]),) * 2) for _ in range(3)]}
        b = A.arm_checks(inst, "B")
        assert all(c in A.arm_checks(inst, "A") for c in b)
        assert A.green_counts(inst, b)[1] <= A.green_counts(inst, A.arm_checks(inst, "A"))[1]
