"""Deviation D1 analysis wrapper. Imports the FROZEN analysis (experiments/failfirst_ext) and
changes nothing in it. Runs only after the frozen gate passes and the frozen analyze.py has
written the registered output.

  python dev1_analyze.py --run-dir DIR [--out evidence/failfirst_ext_dev1.json]

DIR must hold the untouched results.jsonl (sha256 in dev1_keys.json), dev1_results.jsonl from
dev1_runner.py, run_manifest.json, generations.jsonl and audit.json.

Variants (all committed in DEVIATION.md before any run of this file):
  V1 d1        registered rows + the 15 D1 rows; only the 15 pre-listed "attempt 3 exceeds the
               registered single retry" lines are waived
  V2 drop      registered rows only; the frozen assemble() drops the checks lacking a patch
               verdict; only the "15 expected verdicts missing" integrity line is waived
  V3 green     as V1 with the 15 D1 verdicts set to PASS (exit 0)
  V4 not_green as V1 with the 15 D1 verdicts set to FAIL (exit 1)
Robustness rule: if the four verdicts are not identical, no verdict is claimed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / "failfirst_ext"
sys.path.insert(0, str(FROZEN))
import analyze as A  # noqa: E402  frozen
import common as C  # noqa: E402  frozen

D1_ATTEMPT = 3
DEV1_FILES = {".gitattributes", "DEVIATION.md", "dev1_keys.json", "dev1_runner.py", "dev1_analyze.py"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_variant(name, lock, manifest, gens, audit, rows, waive_problems=(), waive_missing=False):
    insts, n_missing, n_pairs, _first, problems = A.assemble(lock, manifest, rows)
    waived = [p for p in problems if p in set(waive_problems)]
    problems = [p for p in problems if p not in set(waive_problems)]
    problems += A.generation_problems(manifest, gens)
    problems += A.audit_problems(lock, audit)
    models = sorted({g["returned_model"] for g in gens if g.get("ok") and g.get("returned_model")})
    res = A.analyse(insts, audit=audit, n_skipped=lock["n_skipped"], n_walked=lock["n_walked"],
                    returned_models=models, n_missing=0 if waive_missing else n_missing,
                    extra_integrity=problems)
    return {"variant": name, "verdict": res["verdict"], "n_missing_raw": n_missing,
            "missing_waived": bool(waive_missing and n_missing), "problems_waived": waived,
            "n_checks": sum(len(i["checks"]) for i in insts), "n_pairs": n_pairs, **res}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default="evidence/failfirst_ext_dev1.json")
    args = ap.parse_args(argv)
    run_dir = Path(args.run_dir)

    ok, msg = A.prereg_gate()
    if not ok:
        print(f"BLOCKED: frozen gate: {msg}")
        return 3
    own = [ln for ln in (HERE / "DEV1.sha256").read_text(encoding="utf-8").split("\n") if ln]
    listed = {ln.split("  ", 1)[1] for ln in own}
    if listed != DEV1_FILES:
        print(f"BLOCKED: DEV1.sha256 lists {sorted(listed)}, expected {sorted(DEV1_FILES)}")
        return 3
    for ln in own:
        h, n = ln.split("  ", 1)
        if sha(HERE / n) != h:
            print(f"BLOCKED: {n} differs from DEV1.sha256")
            return 3
    spec = json.loads((HERE / "dev1_keys.json").read_text(encoding="utf-8"))
    if sha(run_dir / "results.jsonl") != spec["results_jsonl_sha256"]:
        print("BLOCKED: results.jsonl is not the hashed registered file")
        return 4

    lock = json.loads((FROZEN / "sample.lock.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    rows = A.load_jsonl(run_dir / "results.jsonl")
    gens = A.load_jsonl(run_dir / "generations.jsonl")
    audit_path = run_dir / "audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else None
    if manifest.get("prompt_sha256") != C.sha256_file(FROZEN / "prompt.txt"):
        print("BLOCKED: run manifest was generated with a different prompt.txt")
        return 4

    want = {(k["check_id"], k["target"]) for k in spec["keys"]}
    dev = A.load_jsonl(run_dir / "dev1_results.jsonl")
    dkeys = [(r["check_id"], r["target"]) for r in dev]
    d1_problems = []
    if set(dkeys) != want or len(dkeys) != len(want):
        d1_problems.append(f"D1 rows {len(dkeys)} do not match the {len(want)} pre-listed runs one-to-one")
    for r in dev:
        if r.get("attempt") != D1_ATTEMPT or r.get("deviation") != "D1":
            d1_problems.append(f"{r['check_id']} {r['target']}: not a D1 attempt-3 row")
        if not C.row_completed(r):
            d1_problems.append(f"{r['check_id']} {r['target']}: D1 run not completed")
    waive = [f"{k}: attempt {D1_ATTEMPT} exceeds the registered single retry" for k in sorted(want)]

    def forced(code):
        out = copy.deepcopy(dev)
        for r in out:
            r["exit_code"], r["timed_out"], r["assertion_error"] = code, False, False
        return out

    variants = [
        run_variant("V1_d1", lock, manifest, gens, audit, rows + dev, waive_problems=waive),
        run_variant("V2_drop", lock, manifest, gens, audit, rows, waive_missing=True),
        run_variant("V3_all_green", lock, manifest, gens, audit, rows + forced(0), waive_problems=waive),
        run_variant("V4_all_not_green", lock, manifest, gens, audit, rows + forced(1), waive_problems=waive),
    ]
    if variants[1]["n_missing_raw"] != len(want):
        variants[1]["integrity_failures"] = variants[1]["integrity_failures"] + [
            f"V2: {variants[1]['n_missing_raw']} missing verdicts, not the {len(want)} pre-listed"]
        variants[1]["verdict"] = "BLOCKED"
    for v in variants[:1] + variants[2:]:
        if d1_problems:
            v["integrity_failures"] = v["integrity_failures"] + d1_problems
            v["verdict"] = "BLOCKED"
    verdicts = [v["verdict"] for v in variants]
    claimed = verdicts[0] if len(set(verdicts)) == 1 else "NO VERDICT CLAIMED"
    evidence = {
        "task_id": C.TASK_ID, "deviation": "D1",
        "registered_status": "BLOCKED (15 verdicts missing after the registered retry)",
        "frozen_prereg_sha256": C.sha256_file(FROZEN / "PREREG.md"),
        "results_jsonl_sha256": spec["results_jsonl_sha256"],
        "dev1_results_sha256": sha(run_dir / "dev1_results.jsonl"),
        "d1_rows": [{k: r.get(k) for k in ("check_id", "target", "status", "applied", "d1_markers",
                                           "setup_file", "started_utc")} for r in dev],
        "d1_problems": d1_problems,
        "verdicts": dict(zip([v["variant"] for v in variants], verdicts)),
        "robustness_rule": "all four verdicts identical, else no verdict claimed",
        "claimed_verdict_under_d1": claimed,
        "variants": variants,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(A.denan(evidence), indent=1, sort_keys=True, allow_nan=False, default=str) + "\n",
                   encoding="utf-8", newline="\n")
    for v in variants:
        print(f"{v['variant']}: {v['verdict']} D={v['primary']['delta_fgs']} CI95={v['primary']['ci95']}")
    print(f"claimed under D1: {claimed} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
