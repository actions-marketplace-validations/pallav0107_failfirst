"""Oracle audit: re-run the official SWE-bench harness on a seeded, label-stratified sample of
the (instance, patch) pairs (60 resolved + 60 unresolved) and compare with the published labels.

  python audit_oracle.py prepare --run-dir DIR (--lock sample.lock.json | --pilot-file F)
      -> DIR/audit/selection.json and DIR/audit/batch_<k>.jsonl (one prediction per instance
         per batch, because the harness keys predictions by instance id)
  # on the Docker host, inside a venv with swebench==SWEBENCH_VERSION, for EVERY batch, always
  # with the single run id RUN_ID (submissions differ in model name, so reports never collide):
  #   python -m swebench.harness.run_evaluation --dataset_name princeton-nlp/SWE-bench_Verified \
  #     --split test --predictions_path batch_<k>.jsonl --run_id ffx_audit --max_workers 4 \
  #     --namespace swebench --cache_level instance --timeout 1800
  python audit_oracle.py collect --run-dir DIR --logs LOGDIR/run_evaluation
      -> DIR/audit.json {n, agree, by_label, missing, pairs}

A pair without a report under RUN_ID counts as a disagreement (missing evidence is not PASS).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

SWEBENCH_VERSION = "4.1.0"
PER_LABEL = 60
RUN_ID = "ffx_audit"
MODEL_PREFIX = "ffx_audit__"


def select_pairs(instances: list[dict], seed: int = C.SEED, per_label: int = PER_LABEL) -> list[dict]:
    """Seeded stratified draw: one random.Random(seed) draws `per_label` resolved pairs from the
    sorted resolved pairs, then `per_label` unresolved pairs from the sorted unresolved pairs."""
    rng = random.Random(seed)
    out = []
    for label in ("resolved", "unresolved"):
        pool = sorted((i["instance_id"], p["submission"]) for i in instances for p in i["patches"]
                      if p["label"] == label)
        k = min(per_label, len(pool))
        out += [{"instance_id": a, "submission": b, "label": label} for a, b in rng.sample(pool, k)]
    return sorted(out, key=lambda p: (p["instance_id"], p["submission"]))


def batches(pairs: list[dict]) -> list[list[dict]]:
    """Greedy split so that no instance appears twice in a batch (deterministic)."""
    out: list[list[dict]] = []
    for p in pairs:
        for b in out:
            if all(q["instance_id"] != p["instance_id"] for q in b):
                b.append(p)
                break
        else:
            out.append([p])
    return out


def cmd_prepare(args) -> int:
    import fetch_patches as F
    ok, msg = C.prereg_gate(C.HERE, require_frozen=bool(args.lock))
    if not ok:
        print(msg + " -- refusing to prepare the audit")
        return 3
    if args.lock:
        ok, msg = C.lock_gate(C.HERE, args.lock)
        if not ok:
            print(msg)
            return 3
        instances = json.loads(Path(args.lock).read_text(encoding="utf-8"))["instances"]
        per_label = PER_LABEL
    else:
        instances = json.loads(Path(args.pilot_file).read_text(encoding="utf-8"))["instances"]
        pilot = set(C.read_lines(C.HERE / "pilot_ids.txt"))
        if any(i["instance_id"] not in pilot for i in instances):
            print("BLOCKED: pilot file contains non-pilot ids")
            return 2
        per_label = args.per_label
    pool = F.fetch_pool()
    pairs = select_pairs(instances, per_label=per_label)
    adir = Path(args.run_dir) / "audit"
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "selection.json").write_text(json.dumps({"seed": C.SEED, "per_label": per_label,
                                                     "run_id": RUN_ID, "pairs": pairs}, indent=1),
                                         encoding="utf-8")
    bs = batches(pairs)
    for k, b in enumerate(bs):
        with (adir / f"batch_{k}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
            for p in b:
                patch = F.fetch_patch(pool, p["submission"], p["instance_id"])
                fh.write(json.dumps({"instance_id": p["instance_id"],
                                     "model_name_or_path": MODEL_PREFIX + p["submission"],
                                     "model_patch": patch}) + "\n")
    print(f"audit: {len(pairs)} pairs in {len(bs)} batches, run id {RUN_ID} -> {adir}")
    return 0


def report_path(logs: Path, run_id: str, submission: str, instance_id: str) -> Path:
    return logs / run_id / f"{MODEL_PREFIX}{submission}" / instance_id / "report.json"


def summarise(rows: list[dict]) -> dict:
    by_label = {}
    for label in ("resolved", "unresolved"):
        rs = [r for r in rows if r["label"] == label]
        by_label[label] = {"n": len(rs), "agree": sum(1 for r in rs if r["agree"])}
    return {"n": len(rows), "agree": sum(1 for r in rows if r["agree"]),
            "missing": sum(1 for r in rows if r.get("rerun", "x") is None),
            "by_label": by_label, "swebench_version": SWEBENCH_VERSION, "run_id": RUN_ID, "pairs": rows}


def collect(pairs: list[dict], logs: Path, run_id: str = RUN_ID) -> dict:
    rows = []
    for p in pairs:
        rep = report_path(Path(logs), run_id, p["submission"], p["instance_id"])
        rerun = None
        if rep.exists():
            data = json.loads(rep.read_text(encoding="utf-8"))
            rerun = "resolved" if (data.get(p["instance_id"]) or {}).get("resolved") else "unresolved"
        rows.append(dict(p, rerun=rerun, agree=rerun == p["label"]))
    return summarise(rows)


def cmd_collect(args) -> int:
    adir = Path(args.run_dir) / "audit"
    sel = json.loads((adir / "selection.json").read_text(encoding="utf-8"))
    res = collect(sel["pairs"], Path(args.logs), sel.get("run_id", RUN_ID))
    (Path(args.run_dir) / "audit.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"audit: agree {res['agree']}/{res['n']} by label {res['by_label']} (missing {res['missing']})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare")
    p.add_argument("--run-dir", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--lock")
    g.add_argument("--pilot-file")
    p.add_argument("--per-label", type=int, default=PER_LABEL)
    c = sp.add_parser("collect")
    c.add_argument("--run-dir", required=True)
    c.add_argument("--logs", required=True)
    args = ap.parse_args(argv)
    return cmd_prepare(args) if args.cmd == "prepare" else cmd_collect(args)


if __name__ == "__main__":
    sys.exit(main())
