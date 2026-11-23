"""Unblinded analysis for the fail-first SWE-bench Verified experiment.

Refuses to run unless EVERY file of this folder matches the frozen PREREG.sha256 that sits
next to THIS file (so a copied directory is judged on its own contents) and no unfrozen file
exists. Labels are joined to verdicts only here.

  python analyze.py --dry-run              # gate + built-in known-answer self-test + readiness
  python analyze.py --run-dir DIR          # full analysis -> evidence/failfirst_ext.json
  python analyze.py --pilot-report DIR     # registered pilot rule (allowed before the freeze)

Exit codes: 0 ok, 3 BLOCKED by the prereg gate, 4 BLOCKED by an inconsistent run.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

BOOTSTRAP_RESAMPLES = 10_000
PLACEBO_DRAWS = 1_000
PRACTICAL_PP = 0.10           # 10 percentage points
S1_FLOOR = 0.05               # AGAINST if the vacuous share's upper bound is below 5%
AUDIT_MIN_AGREE = 0.95        # per label
AUDIT_PER_LABEL = 60
MAX_SKIP_SHARE = 0.20
MAX_EXEC_ATTEMPTS = 2         # one retry for a missing execution row
MAX_GEN_ATTEMPTS = 3          # one reply + at most two regenerations
PILOT_BM25_THRESHOLD = 0.60
UNFIXED_TARGETS = ("unfixed1", "unfixed2")


def prereg_gate(base: Path = HERE) -> tuple[bool, str]:
    return C.prereg_gate(base, require_frozen=True)


# =========================================================================== model
# An instance is a dict:
#   {"instance_id", "repo", "labels": {patch_id: "resolved"|"unresolved"},
#    "checks": [{"check_id", "unfixed": (o1, o2), "strict_fail": bool,
#                "patched": {patch_id: (outcome, applied)}, "gold": outcome|None}]}

def unfixed_outcome(check: dict) -> str:
    o1, o2 = check["unfixed"]
    return C.combine_unfixed(o1, o2)


def arm_checks(inst: dict, arm: str) -> list[dict]:
    if arm == "A":
        return list(inst["checks"])
    if arm == "B":
        return [c for c in inst["checks"] if C.in_failfirst_arm(unfixed_outcome(c))]
    if arm == "N":     # A minus the PASS-on-unfixed checks (FAIL or ERROR on unfixed)
        return [c for c in inst["checks"] if unfixed_outcome(c) != C.PASS]
    if arm == "S":     # S5 strict: FAIL only when the script itself raised AssertionError (both runs)
        return [c for c in inst["checks"]
                if C.in_failfirst_arm(unfixed_outcome(c)) and c.get("strict_fail")]
    raise ValueError(arm)


def green_counts(inst: dict, checks: list[dict]) -> tuple[int, int, int, int, int]:
    """(green on unresolved, green total, pairs on unresolved, green on resolved, pairs on resolved)."""
    gu = g = pu = gr = pr = 0
    for c in checks:
        for pid, (outcome, applied) in c["patched"].items():
            green = C.is_green(outcome, applied)
            if inst["labels"][pid] == "unresolved":
                pu += 1
                gu += green
            else:
                pr += 1
                gr += green
            g += green
    return gu, g, pu, gr, pr


def instance_vector(inst: dict) -> dict:
    """Per-instance sufficient statistics; every statistic below is a ratio of their sums."""
    a = green_counts(inst, arm_checks(inst, "A"))
    b = green_counts(inst, arm_checks(inst, "B"))
    nn = green_counts(inst, arm_checks(inst, "N"))
    s = green_counts(inst, arm_checks(inst, "S"))
    outs = [unfixed_outcome(c) for c in inst["checks"]]
    gold_ok = sum(1 for c in inst["checks"] if unfixed_outcome(c) == C.FAIL and c.get("gold") == C.PASS)
    return {
        "a_gu": a[0], "a_g": a[1], "a_pu": a[2], "a_gr": a[3], "a_pr": a[4],
        "b_gu": b[0], "b_g": b[1], "b_pu": b[2], "b_gr": b[3], "b_pr": b[4],
        "n_gu": nn[0], "n_g": nn[1],
        "s_gu": s[0], "s_g": s[1],
        "n_checks": len(outs), "n_b": len(arm_checks(inst, "B")),
        "n_pass": outs.count(C.PASS), "n_fail": outs.count(C.FAIL), "n_error": outs.count(C.ERROR),
        "all_vacuous": int(len(outs) > 0 and all(o == C.PASS for o in outs)),
        "no_failfirst": int(not any(o == C.FAIL for o in outs)),
        "gold_ok": gold_ok,
    }


def _ratio(num: float, den: float) -> float:
    return num / den if den else float("nan")


def stats_from_sums(t: dict) -> dict:
    fgs_a = _ratio(t["a_gu"], t["a_g"])
    fgs_b = _ratio(t["b_gu"], t["b_g"])
    fgs_n = _ratio(t["n_gu"], t["n_g"])
    fgs_s = _ratio(t["s_gu"], t["s_g"])
    return {
        "fgs_a": fgs_a, "fgs_b": fgs_b, "delta": fgs_a - fgs_b,
        "part_pass": fgs_a - fgs_n, "part_error": fgs_n - fgs_b,
        "fgs_strict": fgs_s, "delta_strict": fgs_a - fgs_s,
        "fpr_a": _ratio(t["a_gu"], t["a_pu"]), "fpr_b": _ratio(t["b_gu"], t["b_pu"]),
        "tpr_a": _ratio(t["a_gr"], t["a_pr"]), "tpr_b": _ratio(t["b_gr"], t["b_pr"]),
        "vacuous_share": _ratio(t["n_pass"], t["n_checks"]),
        "residual": _ratio(t["b_gu"], t["b_pu"]),
        "kept_share": _ratio(t["b_gr"], t["a_gr"]),
        "error_share": _ratio(t["n_error"], t["n_checks"]),
        "gold_share": _ratio(t["gold_ok"], t["n_checks"]),
    }


def sum_vectors(vecs: list[dict], idx=None) -> dict:
    keys = vecs[0].keys()
    out = dict.fromkeys(keys, 0)
    for i in (idx if idx is not None else range(len(vecs))):
        v = vecs[i]
        for k in keys:
            out[k] += v[k]
    return out


def percentile(sorted_vals: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (numpy's default), stdlib only."""
    if not sorted_vals:
        return float("nan")
    pos = (len(sorted_vals) - 1) * q / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def cluster_bootstrap(vecs: list[dict], keys: tuple[str, ...], resamples: int = BOOTSTRAP_RESAMPLES,
                      seed: int = C.SEED) -> dict:
    """Instance-cluster percentile bootstrap. Indices from random.Random(seed); resamples where a
    statistic is undefined (0 denominator) are dropped for that statistic and counted."""
    rng = random.Random(seed)
    n = len(vecs)
    draws = {k: [] for k in keys}
    undefined = Counter()
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        st = stats_from_sums(sum_vectors(vecs, idx))
        for k in keys:
            v = st[k]
            if math.isnan(v):
                undefined[k] += 1
            else:
                draws[k].append(v)
    return {k: {"ci95": [percentile(sorted(draws[k]), 2.5), percentile(sorted(draws[k]), 97.5)],
                "undefined": undefined[k]} for k in keys}


def placebo(insts: list[dict], vecs: list[dict], draws: int = PLACEBO_DRAWS,
            seed: int = C.SEED + 1) -> dict:
    """Instance-stratified size-matched random filter, used as a null distribution. In each
    draw, every instance keeps as many checks, chosen uniformly at random among its own checks,
    as arm B keeps there; D_P = FGS_A - FGS_P on the observed instances (no resampling)."""
    rng = random.Random(seed)
    per_check = [[green_counts(inst, [c])[:2] for c in inst["checks"]] for inst in insts]
    tot = sum_vectors(vecs)
    fgs_a = _ratio(tot["a_gu"], tot["a_g"])
    vals, undefined = [], 0
    for _ in range(draws):
        p_gu = p_g = 0
        for v, cks in zip(vecs, per_check):
            for j in rng.sample(range(len(cks)), v["n_b"]):
                p_gu += cks[j][0]
                p_g += cks[j][1]
        d = fgs_a - _ratio(p_gu, p_g)
        if math.isnan(d):
            undefined += 1
        else:
            vals.append(d)
    vals.sort()
    return {"draws": draws, "delta_mean": (sum(vals) / len(vals)) if vals else float("nan"),
            "ci95": [percentile(vals, 2.5), percentile(vals, 97.5)], "p975": percentile(vals, 97.5),
            "undefined": undefined, "stratified_by": "instance"}


def decide(delta: float, ci: list[float], placebo_p975: float, s1_ci_hi: float,
           integrity: list[str]) -> str:
    """The registered rule. Precedence: BLOCKED, AGAINST, SUPPORTED, INCONCLUSIVE."""
    if integrity:
        return "BLOCKED"
    lo, hi = ci
    if any(math.isnan(x) for x in (delta, lo, hi)):
        return "INCONCLUSIVE"
    if hi < PRACTICAL_PP or hi < 0 or (not math.isnan(s1_ci_hi) and s1_ci_hi < S1_FLOOR):
        return "AGAINST"
    if lo > 0 and delta >= PRACTICAL_PP and not math.isnan(placebo_p975) and delta > placebo_p975:
        return "SUPPORTED"
    return "INCONCLUSIVE"


def integrity_failures(*, audit: dict | None, n_skipped: int, n_walked: int,
                       returned_models: list[str], n_missing: int, extra: list[str] = ()) -> list[str]:
    bad = list(extra)
    if audit is None or not audit.get("n"):
        bad.append("oracle audit missing")
    else:
        for label, st in sorted((audit.get("by_label") or {}).items()):
            if not st.get("n") or st["agree"] < AUDIT_MIN_AGREE * st["n"]:
                bad.append(f"oracle audit agreement for {label} {st.get('agree')}/{st.get('n')} < 95%")
        if not audit.get("by_label"):
            bad.append("oracle audit has no per-label agreement")
    if n_walked and n_skipped > MAX_SKIP_SHARE * n_walked:
        bad.append(f"{n_skipped}/{n_walked} walked instances skipped (> 20%)")
    if len(set(returned_models)) != 1:
        bad.append(f"check-writer returned {len(set(returned_models))} distinct model strings")
    if n_missing:
        bad.append(f"{n_missing} expected verdicts missing after the registered retry")
    return bad


def analyse(insts: list[dict], *, audit: dict | None, n_skipped: int, n_walked: int,
            returned_models: list[str], n_missing: int, extra_integrity: list[str] = (),
            resamples: int = BOOTSTRAP_RESAMPLES, placebo_draws: int = PLACEBO_DRAWS) -> dict:
    vecs = [instance_vector(i) for i in insts]
    tot = sum_vectors(vecs)
    point = stats_from_sums(tot)
    boot = cluster_bootstrap(vecs, ("delta", "vacuous_share", "residual", "kept_share",
                                    "delta_strict", "error_share", "fpr_a", "fpr_b", "tpr_a", "tpr_b",
                                    "part_pass", "part_error"), resamples=resamples)
    plc = placebo(insts, vecs, draws=placebo_draws)
    integrity = integrity_failures(audit=audit, n_skipped=n_skipped, n_walked=n_walked,
                                   returned_models=returned_models, n_missing=n_missing,
                                   extra=list(extra_integrity))
    verdict = decide(point["delta"], boot["delta"]["ci95"], plc["p975"],
                     boot["vacuous_share"]["ci95"][1], integrity)
    by_repo = defaultdict(list)
    for inst, v in zip(insts, vecs):
        by_repo[inst["repo"]].append(v)
    n = len(insts)
    return {
        "verdict": verdict, "integrity_failures": integrity,
        "unfixed_outcomes": {"PASS": tot["n_pass"], "FAIL": tot["n_fail"], "ERROR": tot["n_error"]},
        "arms": {
            "unfiltered": {"n_checks": tot["n_checks"], "n_green": tot["a_g"],
                           "n_green_unresolved": tot["a_gu"], "fgs": point["fgs_a"]},
            "failfirst": {"n_checks": tot["n_b"], "n_green": tot["b_g"],
                          "n_green_unresolved": tot["b_gu"], "fgs": point["fgs_b"]},
        },
        "primary": {"metric": "FGS_A - FGS_B", "delta_fgs": point["delta"],
                    "ci95": boot["delta"]["ci95"], "bootstrap_resamples": resamples,
                    "bootstrap_undefined": boot["delta"]["undefined"],
                    "cluster": "instance", "seed": C.SEED},
        "placebo": {"delta_mean": plc["delta_mean"], "ci95": plc["ci95"], "p975": plc["p975"],
                    "draws": plc["draws"], "undefined": plc["undefined"], "stratified_by": "instance",
                    "seed": C.SEED + 1},
        "secondary": {
            "vacuous_share": point["vacuous_share"], "vacuous_share_ci95": boot["vacuous_share"]["ci95"],
            "all_vacuous_instance_share": _ratio(tot["all_vacuous"], n),
            "residual_false_green_rate": point["residual"], "residual_ci95": boot["residual"]["ci95"],
            "kept_resolved_green_share": point["kept_share"], "kept_ci95": boot["kept_share"]["ci95"],
            "no_failfirst_instance_share": _ratio(tot["no_failfirst"], n),
            "fpr": {"unfiltered": point["fpr_a"], "failfirst": point["fpr_b"]},
            "fpr_ci95": {"unfiltered": boot["fpr_a"]["ci95"], "failfirst": boot["fpr_b"]["ci95"]},
            "tpr": {"unfiltered": point["tpr_a"], "failfirst": point["tpr_b"]},
            "tpr_ci95": {"unfiltered": boot["tpr_a"]["ci95"], "failfirst": boot["tpr_b"]["ci95"]},
            "decomposition": {"from_removing_pass_on_unfixed": point["part_pass"],
                              "from_removing_error_on_unfixed": point["part_error"],
                              "pass_ci95": boot["part_pass"]["ci95"],
                              "error_ci95": boot["part_error"]["ci95"]},
            "strict_delta_fgs": point["delta_strict"], "strict_ci95": boot["delta_strict"]["ci95"],
            "fail_unfixed_pass_gold_share": point["gold_share"],
            "error_share": point["error_share"], "error_ci95": boot["error_share"]["ci95"],
            "by_repo": {r: dict(n_instances=len(vs), **{k: stats_from_sums(sum_vectors(vs))[k]
                                                       for k in ("fgs_a", "fgs_b", "vacuous_share",
                                                                 "error_share")})
                        for r, vs in sorted(by_repo.items())},
        },
    }


# =========================================================================== run inputs

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def select_rows(rows: list[dict]) -> tuple[dict, list[str]]:
    """Registered rerun rule. Per (check, target): attempts are numbered 1..2 with no repeats;
    at most ONE completed attempt may exist (a second completed row is a silent rerun and
    BLOCKS); the completed attempt is the verdict. Returns ({key: row}, problems)."""
    by_key = defaultdict(list)
    for r in rows:
        by_key[(r["check_id"], r["target"])].append(r)
    chosen, problems = {}, []
    for key, rs in by_key.items():
        attempts = [r.get("attempt", 1) for r in rs]
        if len(set(attempts)) != len(attempts):
            problems.append(f"{key}: repeated attempt number")
        if max(attempts) > MAX_EXEC_ATTEMPTS:
            problems.append(f"{key}: attempt {max(attempts)} exceeds the registered single retry")
        done = sorted((r for r in rs if C.row_completed(r)), key=lambda r: r.get("attempt", 1))
        if len(done) > 1:
            problems.append(f"{key}: duplicate completed rows ({len(done)})")
        if done:
            chosen[key] = done[0]
    return chosen, problems


def _first_exc_strict(rows: list[dict | None]) -> bool:
    return all(r is not None and r.get("assertion_error") for r in rows)


def assemble(lock: dict, manifest: dict, rows: list[dict]):
    """Join the run rows to the locked sample.
    Returns (instances, n_missing, n_pairs, first_utc, problems)."""
    chosen, problems = select_rows(rows)
    first = None
    for r in rows:
        if r.get("started_utc") and (first is None or r["started_utc"] < first):
            first = r["started_utc"]
    checks_by_inst = defaultdict(list)
    for c in manifest["checks"]:
        checks_by_inst[c["instance_id"]].append(c)
    insts, missing, pairs = [], 0, 0
    for li in lock["instances"]:
        iid = li["instance_id"]
        labels = {p["submission"]: p["label"] for p in li["patches"]}
        psha = {p["submission"]: p["patch_sha256"] for p in li["patches"]}
        checks = []
        for mc in sorted(checks_by_inst.get(iid, []), key=lambda c: c["k"]):
            def get(target, want_patch=None):
                nonlocal missing
                r = chosen.get((mc["check_id"], target))
                if r is None or r.get("check_sha256") != mc["check_sha256"] or (
                        want_patch is not None and r.get("patch_sha256") != want_patch):
                    missing += 1
                    return None
                return r
            u = [get(t) for t in UNFIXED_TARGETS]
            if None in u:
                patched_rows = [get("patch:" + s, psha[s]) for s in labels]
                get("gold")
                continue          # an incomplete check is missing, never classified
            unf = tuple(C.classify_run(r["exit_code"], r.get("timed_out", False)) for r in u)
            patched = {}
            for sub in labels:
                r = get("patch:" + sub, psha[sub])
                if r is None:
                    continue
                pairs += 1
                patched[sub] = (C.classify_run(r["exit_code"], r.get("timed_out", False)), True)
            g = get("gold")
            checks.append({"check_id": mc["check_id"], "unfixed": unf, "strict_fail": _first_exc_strict(u),
                           "patched": patched,
                           "gold": C.classify_run(g["exit_code"], g.get("timed_out", False)) if g else None})
        missing += max(0, C.K_CHECKS - len(checks_by_inst.get(iid, []))) * (2 + 6 + 1)
        insts.append({"instance_id": iid, "repo": li["repo"], "labels": labels,
                      "checks": [c for c in checks if len(c["patched"]) == len(labels)]})
    return insts, missing, pairs, first, problems


def generation_problems(manifest: dict, gens: list[dict]) -> list[str]:
    """Each check's file must be the FIRST usable reply of its slot; attempts numbered 0.. with no
    repeats, at most 3, and nothing logged after the first usable reply. A slot with no usable
    reply must hold the registered stub."""
    stub_sha = C.sha256_bytes(STUB_TEXT.encode("utf-8"))
    by_slot = defaultdict(list)
    for g in gens:
        by_slot[(g["instance_id"], g["k"])].append(g)
    problems = []
    for c in manifest["checks"]:
        rows = sorted(by_slot.get((c["instance_id"], c["k"]), []), key=lambda r: r["attempt"])
        att = [r["attempt"] for r in rows]
        tag = c["check_id"]
        if not rows:
            problems.append(f"{tag}: no generation record")
            continue
        if att != list(range(len(att))):
            problems.append(f"{tag}: attempts {att} are not 0..n without repeats")
        if len(rows) > MAX_GEN_ATTEMPTS:
            problems.append(f"{tag}: {len(rows)} generation attempts > {MAX_GEN_ATTEMPTS}")
        usable = [i for i, r in enumerate(rows) if r.get("usable")]
        if usable:
            first = rows[usable[0]]
            if usable[0] != len(rows) - 1:
                problems.append(f"{tag}: replies were requested after the first usable one")
            if first.get("script_sha256") != c["check_sha256"]:
                problems.append(f"{tag}: check file is not the first usable reply")
            if c.get("generation_failed"):
                problems.append(f"{tag}: marked failed but has a usable reply")
        elif not (c.get("generation_failed") and c["check_sha256"] == stub_sha):
            problems.append(f"{tag}: no usable reply but the check is not the registered stub")
    return problems


#: Must equal generate.STUB (kept here so the analysis does not import the generator).
STUB_TEXT = "import sys\nsys.exit(127)  # no usable reply from the check-writer\n"


def audit_problems(lock: dict, audit: dict | None) -> list[str]:
    """The audited pairs must be exactly the seeded stratified selection from the frozen lock."""
    import audit_oracle as AO
    if not audit:
        return ["oracle audit missing"]
    want = {(p["instance_id"], p["submission"], p["label"]) for p in AO.select_pairs(lock["instances"])}
    got = [(p["instance_id"], p["submission"], p["label"]) for p in audit.get("pairs", [])]
    problems = []
    if len(got) != len(set(got)):
        problems.append("oracle audit lists a pair twice")
    if set(got) != want:
        problems.append(f"oracle audit pairs differ from the seeded selection "
                        f"({len(set(got) - want)} extra, {len(want - set(got))} absent)")
    if audit.get("n") != 2 * AUDIT_PER_LABEL:
        problems.append(f"oracle audit n={audit.get('n')} != {2 * AUDIT_PER_LABEL}")
    for label in ("resolved", "unresolved"):
        st = (audit.get("by_label") or {}).get(label) or {}
        if st.get("n") != AUDIT_PER_LABEL or st.get("agree", 0) < AUDIT_MIN_AGREE * AUDIT_PER_LABEL:
            problems.append(f"oracle audit {label}: {st.get('agree')}/{st.get('n')} "
                            f"(need n={AUDIT_PER_LABEL} and >= 95%)")
    return problems


def denan(obj):
    """JSON has no NaN: an undefined ratio is written as null."""
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: denan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [denan(v) for v in obj]
    return obj


def run_full(run_dir: Path, out_path: Path, lock_path: Path = HERE / "sample.lock.json",
             check_audit_selection: bool = True) -> int:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    rows = load_jsonl(run_dir / "results.jsonl")
    gens = load_jsonl(run_dir / "generations.jsonl")
    audit_path = run_dir / "audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else None
    prompt_sha = C.sha256_file(HERE / "prompt.txt")
    if manifest.get("prompt_sha256") != prompt_sha:
        print("BLOCKED: run manifest was generated with a different prompt.txt")
        return 4
    insts, n_missing, n_pairs, first_utc, problems = assemble(lock, manifest, rows)
    problems += generation_problems(manifest, gens)
    if check_audit_selection:
        problems += audit_problems(lock, audit)
    models = sorted({g["returned_model"] for g in gens if g.get("ok") and g.get("returned_model")})
    res = analyse(insts, audit=audit, n_skipped=lock["n_skipped"], n_walked=lock["n_walked"],
                  returned_models=models, n_missing=n_missing, extra_integrity=problems)
    manifest_sha = C.sha256_bytes(C.canonical_json(manifest))
    for arm in res["arms"].values():
        arm["run_manifest_sha256"] = manifest_sha
        arm["prompt_sha256"] = prompt_sha
    sampled = {i["instance_id"] for i in lock["instances"]}
    evidence = {
        "task_id": C.TASK_ID,
        "prereg_sha256": C.sha256_file(HERE / "PREREG.md"), "prompt_sha256": prompt_sha,
        "sample_lock_sha256": C.sha256_file(lock_path),
        "prereg_n": lock["n_target"], "n_instances": len(insts),
        "n_checks": sum(len(i["checks"]) for i in insts),
        "n_pairs": n_pairs, "n_missing": n_missing, "n_skipped": lock["n_skipped"],
        "n_walked": lock["n_walked"], "first_sampled_run_utc": first_utc,
        "n_exec_rows": len(rows), "n_exec_retries": sum(1 for r in rows if r.get("attempt", 1) > 1),
        "generator": {"endpoint_host": manifest.get("endpoint_host"),
                      "model_requested": manifest.get("model_requested"),
                      "returned_models": models,
                      "n_generations": sum(1 for g in gens if g.get("ok") and g.get("instance_id") in sampled),
                      "n_regenerations": sum(1 for g in gens if g.get("attempt", 0) > 0),
                      "params": manifest.get("params")},
        "oracle": {"source": f"{C.LABELS_REPO} results.json", "source_commit": C.LABELS_COMMIT,
                   "audit": {"n": (audit or {}).get("n", 0), "agree": (audit or {}).get("agree", 0),
                             "by_label": (audit or {}).get("by_label")}},
        **res,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(denan(evidence), indent=1, sort_keys=True, allow_nan=False,
                                   default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"verdict {res['verdict']}: D={res['primary']['delta_fgs']} CI95={res['primary']['ci95']} -> {out_path}")
    return 0


# =========================================================================== pilot rule

def pilot_report(manifest: dict, rows: list[dict]) -> dict:
    """Registered pilot rule. A pilot check is BROKEN when its unfixed outcome is ERROR, or when
    both unfixed runs and the gold run all end in a Python exception other than AssertionError
    (the script never reached the behaviour). broken_share > 0.60 => add the BM25 excerpts."""
    chosen, problems = select_rows(rows)
    broken = total = missing = 0
    for c in manifest["checks"]:
        rs = [chosen.get((c["check_id"], t)) for t in (*UNFIXED_TARGETS, "gold")]
        if any(r is None for r in rs):
            missing += 1
            continue
        total += 1
        u = C.combine_unfixed(*(C.classify_run(r["exit_code"], r.get("timed_out", False)) for r in rs[:2]))
        crash = all(r.get("exc_type") not in (None, "AssertionError") and r["exit_code"] != 0 for r in rs)
        broken += (u == C.ERROR) or crash
    share = _ratio(broken, total)
    return {"checks": total, "broken": broken, "missing": missing, "problems": problems,
            "broken_share": share, "threshold": PILOT_BM25_THRESHOLD,
            "add_bm25": (not math.isnan(share)) and share > PILOT_BM25_THRESHOLD}


# =========================================================================== self-test

def known_answer_fixture() -> list[dict]:
    """One instance: one vacuous check, one fail-first check, one right and one wrong patch.
    Arm A greens: vac/right, vac/wrong, ff/right -> FGS_A = 1/3. Arm B greens: ff/right -> 0."""
    return [{
        "instance_id": "fixture__ka-1", "repo": "fixture/ka",
        "labels": {"right": "resolved", "wrong": "unresolved"},
        "checks": [
            {"check_id": "vacuous", "unfixed": (C.PASS, C.PASS), "strict_fail": False,
             "patched": {"right": (C.PASS, True), "wrong": (C.PASS, True)}, "gold": C.PASS},
            {"check_id": "failfirst", "unfixed": (C.FAIL, C.FAIL), "strict_fail": True,
             "patched": {"right": (C.PASS, True), "wrong": (C.FAIL, True)}, "gold": C.PASS},
        ]}]


def self_test() -> None:
    v = sum_vectors([instance_vector(i) for i in known_answer_fixture()])
    st = stats_from_sums(v)
    assert abs(st["fgs_a"] - 1 / 3) < 1e-12 and st["fgs_b"] == 0.0, st
    assert abs(st["delta"] - 1 / 3) < 1e-12 and st["vacuous_share"] == 0.5 and st["residual"] == 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pilot-report", metavar="RUN_DIR")
    ap.add_argument("--run-dir", default=str(C.WORK_DIR / "run"))
    ap.add_argument("--out", default=str(C.REPO_ROOT / "evidence" / "failfirst_ext.json"))
    args = ap.parse_args(argv)
    if args.pilot_report:
        ok, msg = C.prereg_gate(HERE, require_frozen=False)
        if not ok:
            print(msg)
            return 3
        d = Path(args.pilot_report)
        rep = pilot_report(json.loads((d / "run_manifest.json").read_text(encoding="utf-8")),
                           load_jsonl(d / "results.jsonl"))
        print(json.dumps(denan(rep), indent=1))
        return 0
    ok, msg = prereg_gate(HERE)
    if not ok:
        print(msg)
        return 3
    print(msg)
    if args.dry_run:
        self_test()
        print("self-test OK (known-answer fixture: FGS_A=1/3, FGS_B=0, D=1/3)")
        run_dir = Path(args.run_dir)
        for name in ("run_manifest.json", "results.jsonl", "generations.jsonl", "audit.json"):
            print(f"  {'present' if (run_dir / name).exists() else 'PENDING'}: {name}")
        print("DRY RUN OK (no labels were joined)")
        return 0
    return run_full(Path(args.run_dir), Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
