"""Draw (or verify) the pre-registered sample.

Frame   = SWE-bench Verified (verified_ids.txt) minus the 22 pilot ids (pilot_ids.txt).
Order   = random.Random(seed).shuffle(sorted(frame)); walk in that order.
Include = 3 resolved + 3 unresolved patches found per fetch_patches.select_patches, and the
          instance image is not listed in image_failures.json. Otherwise SKIPPED with a reason.
          image_failures.json may only be written by --image-failures-from (entries the pull
          log marks `missing`, i.e. the registry has no such image), and only before the freeze.
Stop    = at N_TARGET included instances.

  python sample.py --seed 20261123                     # writes sample.lock.json
  python sample.py --seed 20261123 --verify sample.lock.json [--deep]
  python sample.py --seed 20261123 --image-failures-from pull_status.tsv

--verify replays the walk from the seed and the frame files, replays every instance's
candidate order against the label pool at the pinned commit (results.json hashes must
match the lock), and re-hashes every cached patch. --deep additionally re-runs the whole
selection for every walked instance against a FRESH, EMPTY cache directory: the pool, every
tried patch, every report.json and every base file are downloaded again, and the recomputed
tried log and chosen patches must equal the lock exactly (no cached outcome is trusted).
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import fetch_patches as F  # noqa: E402

LOCK = C.HERE / "sample.lock.json"
IMAGE_FAILURES = C.HERE / "image_failures.json"


def frame_order(seed: int, verified: list[str], pilot: list[str]) -> list[str]:
    frame = sorted(set(verified) - set(pilot))
    random.Random(seed).shuffle(frame)
    return frame


def load_frame_files() -> tuple[list[str], list[str]]:
    return C.read_lines(C.HERE / "verified_ids.txt"), C.read_lines(C.HERE / "pilot_ids.txt")


def load_image_failures() -> dict:
    if IMAGE_FAILURES.exists():
        return json.loads(IMAGE_FAILURES.read_text(encoding="utf-8"))
    return {}


def build(seed: int, n_target: int = C.N_TARGET, workers: int = 8) -> dict:
    verified, pilot = load_frame_files()
    order = frame_order(seed, verified, pilot)
    pool = F.fetch_pool()
    ds = F.load_dataset()
    img_fail = load_image_failures()

    def one(iid: str) -> dict:
        if iid in img_fail:
            return {"complete": False, "reason": "image unavailable: " + img_fail[iid],
                    "patches": [], "tried": []}
        return F.select_patches(pool, ds[iid], seed=seed)

    walk, instances = [], []
    pos = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        while len(instances) < n_target and pos < len(order):
            batch = order[pos:pos + workers * 2]
            pos += len(batch)
            for iid, res in zip(batch, ex.map(one, batch)):
                if len(instances) >= n_target:
                    break              # computed but beyond the stopping point: not walked
                row = ds[iid]
                entry = {"instance_id": iid, "status": "included" if res["complete"] else "skipped",
                         "reason": res["reason"], "tried": res["tried"],
                         "label_conflict_groups": res.get("label_conflict_groups", [])}
                walk.append(entry)
                if res["complete"]:
                    instances.append({"instance_id": iid, "repo": row["repo"],
                                      "version": str(row["version"]),
                                      "base_commit": row["base_commit"],
                                      "image": C.image_name(iid), "patches": res["patches"]})
                print(f"[{len(walk):3d}] {entry['status']:8s} {iid} {entry['reason'] or ''}",
                      flush=True)
    reasons = collections.Counter((w["reason"] or "").split(":")[0] for w in walk
                                  if w["status"] == "skipped")
    tried_all = [t for w in walk for t in w["tried"]]
    selection_stats = {
        "candidate_results": dict(sorted(collections.Counter(t["result"] for t in tried_all).items())),
        "unresolved_rejected_no_report_evidence": sum(t["result"] == "no_report_evidence" for t in tried_all),
        "label_conflict_rejections": sum(t["result"] == "label_conflict" for t in tried_all),
        "label_conflict_groups": sum(len(w.get("label_conflict_groups", [])) for w in walk),
        "instances_with_label_conflict_group": sum(1 for w in walk if w.get("label_conflict_groups")),
        "repo_mix": dict(sorted(collections.Counter(i["repo"] for i in instances).items())),
    }
    return {
        "task_id": C.TASK_ID, "seed": seed, "n_target": n_target,
        "dataset": {"repo": C.DATASET_REPO, "revision": C.DATASET_REVISION,
                    "sha256": C.DATASET_SHA256},
        "labels": {"repo": C.LABELS_REPO, "commit": C.LABELS_COMMIT, "pool_size": len(pool),
                   "pool": {s: pool[s]["results_sha256"] for s in sorted(pool)}},
        "verified_ids_sha256": C.sha256_file(C.HERE / "verified_ids.txt"),
        "pilot_ids_sha256": C.sha256_file(C.HERE / "pilot_ids.txt"),
        "image_failures": img_fail,
        "n": len(instances), "n_walked": len(walk),
        "n_skipped": sum(1 for w in walk if w["status"] == "skipped"),
        "skip_reasons": dict(sorted(reasons.items())),
        "selection_stats": selection_stats,
        "walk": walk, "instances": instances,
    }


# --------------------------------------------------------------------------- verify

class VerifyError(Exception):
    pass


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise VerifyError(msg)


def replay_tried(pool: dict, iid: str, tried: list[dict], seed: int) -> None:
    """The tried log must be exactly the hash-ordered candidates the rule would visit."""
    need = {"resolved": C.N_RESOLVED, "unresolved": C.N_UNRESOLVED}
    it = iter(tried)
    for sub, label in F.candidate_order(pool, iid, seed):
        if need["resolved"] == 0 and need["unresolved"] == 0:
            break
        if need[label] == 0:
            continue
        t = next(it, None)
        _need(t is not None, f"{iid}: tried log ends early (expected {sub})")
        _need(t["submission"] == sub and t["label"] == label,
              f"{iid}: tried {t['submission']}/{t['label']}, rule says {sub}/{label}")
        if t["result"] == "accepted":
            need[label] -= 1
    _need(next(it, None) is None, f"{iid}: tried log has entries the rule never visits")


def verify(lock: dict, seed: int, deep: bool = False, work: Path = C.WORK_DIR,
           pool: dict | None = None) -> tuple[int, int, int]:
    verified, pilot = load_frame_files()
    _need(lock.get("seed") == seed, f"lock seed {lock.get('seed')} != {seed}")
    _need(lock["verified_ids_sha256"] == C.sha256_file(C.HERE / "verified_ids.txt"),
          "verified_ids.txt changed since the lock was written")
    _need(lock["pilot_ids_sha256"] == C.sha256_file(C.HERE / "pilot_ids.txt"),
          "pilot_ids.txt changed since the lock was written")
    _need(lock["labels"]["commit"] == C.LABELS_COMMIT, "label commit differs from the pin")
    _need(lock["dataset"]["sha256"] == C.DATASET_SHA256, "dataset hash differs from the pin")
    order = frame_order(seed, verified, pilot)
    walked = [w["instance_id"] for w in lock["walk"]]
    _need(walked == order[:len(walked)], "walk order is not the seeded shuffle of the frame")
    included = [w["instance_id"] for w in lock["walk"] if w["status"] == "included"]
    _need(included == [i["instance_id"] for i in lock["instances"]],
          "instances list differs from the included walk entries")
    _need(len(included) == lock["n_target"] == lock["n"], "n differs from the target")
    _need(lock["walk"][-1]["status"] == "included", "walk continued past the stopping point")
    pilot_overlap = len(set(included) & set(pilot))
    _need(lock["n_skipped"] == len(walked) - len(included), "n_skipped inconsistent")

    pool = pool if pool is not None else F.fetch_pool(work)
    for sub, digest in lock["labels"]["pool"].items():
        _need(sub in pool and pool[sub]["results_sha256"] == digest,
              f"label pool entry {sub} missing or its results.json hash changed")
    _need(set(pool) == set(lock["labels"]["pool"]), "label pool membership differs")

    img_fail = lock.get("image_failures") or {}
    for w in lock["walk"]:
        iid = w["instance_id"]
        if iid in img_fail:
            _need(w["status"] == "skipped" and not w["tried"], f"{iid}: image failure not skipped")
            continue
        replay_tried(pool, iid, w["tried"], seed)
        accepted = [t for t in w["tried"] if t["result"] == "accepted"]
        complete = (sum(t["label"] == "resolved" for t in accepted) == C.N_RESOLVED and
                    sum(t["label"] == "unresolved" for t in accepted) == C.N_UNRESOLVED)
        _need(complete == (w["status"] == "included"), f"{iid}: status contradicts its tried log")

    n_patches = 0
    for inst in lock["instances"]:
        ps = inst["patches"]
        _need(len(ps) == 6, f"{inst['instance_id']}: {len(ps)} patches")
        _need(sum(p["label"] == "resolved" for p in ps) == 3, f"{inst['instance_id']}: not 3 resolved")
        _need(len({p["identity"] for p in ps}) == 6, f"{inst['instance_id']}: patches not distinct")
        _need(len({p["submission"] for p in ps}) == 6, f"{inst['instance_id']}: submissions repeat")
        for p in ps:
            sub, iid = p["submission"], inst["instance_id"]
            lab = "resolved" if iid in pool[sub]["resolved"] else (
                "unresolved" if iid in pool[sub]["unresolved"] else None)
            _need(lab == p["label"], f"{iid}/{sub}: label {p['label']} but pool says {lab}")
            text = F.fetch_patch(pool, sub, iid, work)
            _need(text is not None, f"{iid}/{sub}: patch no longer available")
            _need(C.sha256_bytes(text.encode("utf-8")) == p["patch_sha256"], f"{iid}/{sub}: patch hash changed")
            _need(C.patch_identity(text) == p["identity"] and C.patch_is_nonempty(text),
                  f"{iid}/{sub}: patch identity/emptiness differs")
            n_patches += 1
    if deep:
        deep_check(lock, seed, F.load_dataset(work))
    return len(included), pilot_overlap, n_patches


def deep_check(lock: dict, seed: int, ds: dict, pool_fetch=None, selector=None, workers: int = 8) -> None:
    """Recompute every walked instance's selection from scratch in an empty temporary cache."""
    import tempfile
    pool_fetch = pool_fetch or (lambda work: F.fetch_pool(work, refresh=True))
    selector = selector or (lambda pool, inst, work, seed: F.select_patches(pool, inst, work=work, seed=seed))
    with tempfile.TemporaryDirectory(prefix="ffx_deep_") as tmp:
        work = Path(tmp)
        _need(not any(work.iterdir()), "deep cache is not empty")
        pool = pool_fetch(work)
        for sub, digest in lock["labels"]["pool"].items():
            _need(sub in pool and pool[sub]["results_sha256"] == digest,
                  f"deep: pool entry {sub} differs on a fresh download")
        img_fail = lock.get("image_failures") or {}
        walk = [w for w in lock["walk"] if w["instance_id"] not in img_fail]
        patches = {i["instance_id"]: i["patches"] for i in lock["instances"]}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda w: selector(pool, ds[w["instance_id"]], work, seed), walk))
        for w, res in zip(walk, results):
            iid = w["instance_id"]
            _need(res["tried"] == w["tried"], f"deep: {iid} tried log differs on a fresh download")
            _need(res.get("label_conflict_groups", []) == w.get("label_conflict_groups", []),
                  f"deep: {iid} label-conflict groups differ on a fresh download")
            _need(res["complete"] == (w["status"] == "included"), f"deep: {iid} inclusion differs")
            if res["complete"]:
                _need(res["patches"] == patches[iid], f"deep: {iid} chosen patches differ")


def image_failures_from(tsv: Path) -> dict:
    """Only registry-confirmed absences (`missing`) become image failures; throttling and
    transient errors never do."""
    out = {}
    for line in Path(tsv).read_text(encoding="utf-8").splitlines():
        parts = line.split("	")
        if len(parts) >= 2 and parts[1] == "missing":
            out[C.instance_from_image(parts[0])] = "registry reports the image as missing"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--verify", metavar="LOCK")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--image-failures-from", metavar="PULL_STATUS_TSV")
    ap.add_argument("--out", default=str(LOCK))
    args = ap.parse_args(argv)
    if args.image_failures_from:
        if (C.HERE / C.FREEZE_FILE).exists():
            print("BLOCKED: image failures can only be recorded before the freeze")
            return 3
        fails = image_failures_from(Path(args.image_failures_from))
        IMAGE_FAILURES.write_text(json.dumps(fails, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                                  newline="\n")
        print(f"wrote {IMAGE_FAILURES}: {len(fails)} image failures; re-run the walk next")
        return 0
    if args.verify:
        try:
            lock = json.loads(Path(args.verify).read_text(encoding="utf-8"))
            n, overlap, n_p = verify(lock, args.seed, deep=args.deep)
        except FileNotFoundError as exc:
            print(f"SAMPLE FAIL: missing {exc.filename}")
            return 1
        except (VerifyError, KeyError) as exc:
            print(f"SAMPLE FAIL: {exc}")
            return 1
        ok = n == C.N_TARGET and overlap == 0 and n_p == 6 * C.N_TARGET
        print(f"SAMPLE {'OK' if ok else 'FAIL'} n={n} pilot_overlap={overlap} patches={n_p}")
        return 0 if ok else 1
    if args.seed != C.SEED:
        print(f"note: seed {args.seed} is not the registered seed {C.SEED}", file=sys.stderr)
    lock = build(args.seed)
    Path(args.out).write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                              newline="\n")
    print(f"wrote {args.out}: n={lock['n']} walked={lock['n_walked']} skipped={lock['n_skipped']} "
          f"reasons={lock['skip_reasons']}")
    return 0 if lock["n"] == C.N_TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
