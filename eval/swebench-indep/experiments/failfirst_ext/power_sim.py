"""Power simulation for the registered design (planning only; not part of the analysis).

Each simulated instance has K=3 checks and 6 patches (3 resolved, 3 unresolved). A check is
vacuous (passes unfixed; green on each patch with p=0.95), fail-first (fails unfixed) or
erroring (never green). Two dependence models:

  iid        fail-first checks are green on resolved patches with p=0.60 and on unresolved
             patches with p=0.15, independently per (check, patch) pair; type shares fixed.
  clustered  each patch has a latent "fixes the reported symptom" flag shared by all
             fail-first checks of the instance, which agree with it except for 10% noise
             (flag rates set so the marginal green rates are still 0.60 / 0.15); per-instance type shares ~ Dirichlet(10 * shares).
             This is the pessimistic model: greens move together within an instance.

The decision rule is the registered one (analyze.decide), with B bootstrap resamples per
replicate (2,000 here instead of 10,000, to keep the simulation cheap) and the registered
instance-stratified placebo null (200 draws; SUPPORTED needs D above its 97.5th percentile).

Limitation of the ERROR model: here an erroring check is never green, so removing it never
changes FGS and the whole simulated D comes from removing vacuous checks. In real data a
check that is ERROR on the unfixed tree (flaky, timeout) may still be green on some patches;
the analysis reports that part of D separately (decomposition), the simulation does not model it.

  python power_sim.py [--n 100] [--reps 500] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as A  # noqa: E402
import common as C  # noqa: E402

SCENARIOS = {
    # name: (vacuous, fail-first, error) shares
    "plan_30pct_vacuous": (0.30, 0.45, 0.25),
    "plan_10pct_vacuous": (0.10, 0.45, 0.45),
    "10pct_vacuous_low_error": (0.10, 0.65, 0.25),
    "true_delta_10pp": (0.0888, 0.45, 0.4612),
    "null_2pct_vacuous": (0.02, 0.73, 0.25),
}
P_VAC, P_FF_R, P_FF_U, NOISE, DIRICHLET_CONC = 0.95, 0.60, 0.15, 0.10, 10.0


def simulate(rng, n, shares, model):
    """Per-instance arrays: a_gu, a_g, b_gu, b_g, n_pass, n_b, and per-check (gu, g)."""
    shares = np.asarray(shares, float)
    labels = np.array([0, 0, 0, 1, 1, 1])          # 0 resolved, 1 unresolved
    inst = np.zeros((n, 6))
    checks = np.zeros((n, C.K_CHECKS, 2))
    for i in range(n):
        p = rng.dirichlet(DIRICHLET_CONC * shares) if model == "clustered" else shares
        types = rng.choice(3, size=C.K_CHECKS, p=p)
        if model == "clustered":
            # latent flag chosen so that, after the 10% noise, the marginal green rates
            # equal the iid model's (0.60 / 0.15): q(1-e) + (1-q)e = target
            q = (np.where(labels == 0, P_FF_R, P_FF_U) - NOISE) / (1 - 2 * NOISE)
            symptom = rng.random(6) < q
        for k, t in enumerate(types):
            if t == 0:
                green = rng.random(6) < P_VAC
            elif t == 1:
                if model == "clustered":
                    green = symptom ^ (rng.random(6) < NOISE)
                else:
                    green = rng.random(6) < np.where(labels == 0, P_FF_R, P_FF_U)
            else:
                green = np.zeros(6, bool)
            gu, g = float((green & (labels == 1)).sum()), float(green.sum())
            checks[i, k] = (gu, g)
            inst[i, 0] += gu
            inst[i, 1] += g
            if t == 1:
                inst[i, 2] += gu
                inst[i, 3] += g
                inst[i, 5] += 1
            if t == 0:
                inst[i, 4] += 1
    return inst, checks


def _fgs(gu, g):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(g > 0, gu / np.where(g > 0, g, 1), np.nan)


def evaluate(rng, inst, checks, n_boot, n_placebo):
    n = len(inst)
    tot = inst.sum(0)
    d = _fgs(tot[0], tot[1]) - _fgs(tot[2], tot[3])
    idx = rng.integers(0, n, size=(n_boot, n))
    s = inst[idx].sum(1)
    db = _fgs(s[:, 0], s[:, 1]) - _fgs(s[:, 2], s[:, 3])
    db = db[~np.isnan(db)]
    ci = [float(np.percentile(db, 2.5)), float(np.percentile(db, 97.5))] if len(db) else [np.nan, np.nan]
    vac = s[:, 4] / (C.K_CHECKS * n)
    s1_hi = float(np.percentile(vac, 97.5))
    # registered placebo: per instance keep n_b random checks of its own (no resampling)
    nb = inst[:, 5].astype(int)
    ranks = rng.random((n_placebo, n, C.K_CHECKS)).argsort(axis=2).argsort(axis=2)
    keep = ranks < nb[None, :, None]
    p_gu = (checks[None, :, :, 0] * keep).sum((1, 2))
    p_g = (checks[None, :, :, 1] * keep).sum((1, 2))
    pv = _fgs(tot[0], tot[1]) - _fgs(p_gu, p_g)
    pv = pv[~np.isnan(pv)]
    p975 = float(np.percentile(pv, 97.5)) if len(pv) else float("nan")
    return A.decide(float(d), ci, p975, s1_hi, []), float(d), ci


def true_delta(shares, model, seed=1):
    rng = np.random.default_rng(seed)
    inst, _ = simulate(rng, 20_000, shares, model)
    t = inst.sum(0)
    return float(_fgs(t[0], t[1]) - _fgs(t[2], t[3]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=C.N_TARGET)
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--placebo", type=int, default=200)
    ap.add_argument("--out", default=str(C.WORK_DIR / "power_sim.json"))
    args = ap.parse_args(argv)
    rng = np.random.default_rng(C.SEED)
    results = []
    print(f"N={args.n} reps={args.reps} bootstrap={args.boot} placebo={args.placebo}")
    print(f"{'scenario':26s} {'model':9s} {'trueD':>6s} {'P(lo>0)':>8s} {'SUPP':>6s} {'AGAINST':>7s} {'INCONC':>6s}")
    for name, shares in SCENARIOS.items():
        for model in ("iid", "clustered"):
            td = true_delta(shares, model)
            counts = {"SUPPORTED": 0, "AGAINST": 0, "INCONCLUSIVE": 0, "BLOCKED": 0}
            lo_pos = 0
            for _ in range(args.reps):
                inst, checks = simulate(rng, args.n, shares, model)
                verdict, d, ci = evaluate(rng, inst, checks, args.boot, args.placebo)
                counts[verdict] += 1
                lo_pos += ci[0] > 0
            row = {"scenario": name, "shares": shares, "model": model, "true_delta": td,
                   "p_ci_lo_gt_0": lo_pos / args.reps,
                   **{f"p_{k.lower()}": v / args.reps for k, v in counts.items()}}
            results.append(row)
            print(f"{name:26s} {model:9s} {td:6.3f} {row['p_ci_lo_gt_0']:8.3f} {row['p_supported']:6.3f} "
                  f"{row['p_against']:7.3f} {row['p_inconclusive']:6.3f}", flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"n": args.n, "reps": args.reps, "boot": args.boot,
                               "placebo": args.placebo, "seed": C.SEED, "results": results}, indent=1),
                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
