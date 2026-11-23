"""EXPLORATORY, NOT PREREGISTERED. Written 24 Nov 2026, after every outcome of the
failfirst_ext experiment was known, at the request of mock reviewers.

Question: if a check must not only fail on the unfixed code (fail-first, arm B) but also
pass on the benchmark's reference fix (arm G, the SWE-bench "fail-to-pass" validation),
how much lower is the false-green share? This asks whether the oracle, not the fail-first
step, is the bottleneck. A practitioner usually has no reference fix before the work, so
arm G is a diagnostic, not a practice the article can recommend as-is.

Inputs are exactly those of deviation D1 variant V1 (registered rows + the 15 D1 rows).
The frozen analysis (experiments/failfirst_ext) and the D1 wrapper are imported, never
modified. The script first reproduces V1's published FGS_A and FGS_B from
evidence/failfirst_ext_dev1.json and refuses to report anything if they differ.

  python experiments/failfirst_ext_explore/explore_gold.py
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "experiments" / "failfirst_ext"
DEV1 = ROOT / "experiments" / "failfirst_ext_dev1"
RUN = ROOT / "evidence" / "failfirst_ext_run"
PUBLISHED = ROOT / "evidence" / "failfirst_ext_dev1.json"
OUT = ROOT / "evidence" / "failfirst_ext_explore.json"
sys.path.insert(0, str(FROZEN))
import analyze as A  # noqa: E402  frozen, imported only
import common as C  # noqa: E402  frozen, imported only


def gold_arm(inst: dict) -> list[dict]:
    return [c for c in inst["checks"]
            if A.unfixed_outcome(c) == C.FAIL and c.get("gold") == C.PASS]


def vector(inst: dict) -> dict:
    a = A.green_counts(inst, A.arm_checks(inst, "A"))
    b = A.green_counts(inst, A.arm_checks(inst, "B"))
    g = A.green_counts(inst, gold_arm(inst))
    v = {}
    for name, t in (("a", a), ("b", b), ("g", g)):
        v.update({f"{name}_gu": t[0], f"{name}_g": t[1], f"{name}_pu": t[2],
                  f"{name}_gr": t[3], f"{name}_pr": t[4]})
    v["n_checks"] = len(inst["checks"])
    v["n_g"] = len(gold_arm(inst))
    return v


def ratio(n: float, d: float) -> float:
    return n / d if d else float("nan")


def stats(t: dict) -> dict:
    s = {}
    for name in ("a", "b", "g"):
        s[f"fgs_{name}"] = ratio(t[f"{name}_gu"], t[f"{name}_g"])
        s[f"fpr_{name}"] = ratio(t[f"{name}_gu"], t[f"{name}_pu"])
        s[f"tpr_{name}"] = ratio(t[f"{name}_gr"], t[f"{name}_pr"])
    s["delta_ag"] = s["fgs_a"] - s["fgs_g"]
    s["delta_bg"] = s["fgs_b"] - s["fgs_g"]
    s["kept_resolved_g"] = ratio(t["g_gr"], t["a_gr"])
    s["g_check_share"] = ratio(t["n_g"], t["n_checks"])
    return s


def total(vecs: list[dict], idx=None) -> dict:
    out = dict.fromkeys(vecs[0], 0)
    for i in (idx if idx is not None else range(len(vecs))):
        for k, val in vecs[i].items():
            out[k] += val
    return out


def bootstrap(vecs: list[dict], keys: tuple[str, ...], resamples: int = 10000) -> dict:
    rng = random.Random(C.SEED)
    n = len(vecs)
    draws = {k: [] for k in keys}
    for _ in range(resamples):
        st = stats(total(vecs, [rng.randrange(n) for _ in range(n)]))
        for k in keys:
            if not math.isnan(st[k]):
                draws[k].append(st[k])
    return {k: [A.percentile(sorted(d), 2.5), A.percentile(sorted(d), 97.5)] for k, d in draws.items()}


def main() -> int:
    lock = json.loads((FROZEN / "sample.lock.json").read_text(encoding="utf-8"))
    manifest = json.loads((RUN / "run_manifest.json").read_text(encoding="utf-8"))
    rows = A.load_jsonl(RUN / "results.jsonl") + A.load_jsonl(RUN / "dev1_results.jsonl")
    insts, *_ = A.assemble(lock, manifest, rows)
    vecs = [vector(i) for i in insts]
    point = stats(total(vecs))

    pub = {x["variant"]: x for x in json.loads(PUBLISHED.read_text(encoding="utf-8"))["variants"]}["V1_d1"]
    want_a, want_b = pub["arms"]["unfiltered"]["fgs"], pub["arms"]["failfirst"]["fgs"]
    if abs(point["fgs_a"] - want_a) > 1e-12 or abs(point["fgs_b"] - want_b) > 1e-12:
        print(f"BLOCKED: cannot reproduce V1 (A {point['fgs_a']} vs {want_a}, B {point['fgs_b']} vs {want_b})")
        return 3

    ci = bootstrap(vecs, ("fgs_g", "delta_ag", "delta_bg"))
    t = total(vecs)
    out = {
        "status": "EXPLORATORY, NOT PREREGISTERED; computed after all outcomes were known",
        "inputs": "deviation D1 variant V1 rows (results.jsonl + dev1_results.jsonl)",
        "reproduced_v1": {"fgs_a": point["fgs_a"], "fgs_b": point["fgs_b"]},
        "arm_g_definition": "check FAILs on the unfixed code (both runs) and PASSes on the reference fix",
        "n_instances": len(vecs), "n_checks": t["n_checks"], "n_checks_g": t["n_g"],
        "point": point, "ci95_instance_bootstrap": ci, "bootstrap_seed": C.SEED,
        "counts": {k: t[k] for k in t},
    }
    OUT.write_text(json.dumps(A.denan(out), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    p = point
    print(f"reproduced V1: FGS_A {p['fgs_a']:.4f}  FGS_B {p['fgs_b']:.4f}")
    print(f"arm G: {t['n_g']}/{t['n_checks']} checks; FGS_G {p['fgs_g']:.4f} CI {ci['fgs_g']}")
    print(f"FPR A/B/G {p['fpr_a']:.3f}/{p['fpr_b']:.3f}/{p['fpr_g']:.3f}  "
          f"TPR A/B/G {p['tpr_a']:.3f}/{p['tpr_b']:.3f}/{p['tpr_g']:.3f}")
    print(f"delta A-G {p['delta_ag']:.4f} CI {ci['delta_ag']}; B-G {p['delta_bg']:.4f} CI {ci['delta_bg']}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
