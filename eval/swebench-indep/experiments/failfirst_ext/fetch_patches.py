"""Fetch public SWE-bench material: the label pool, candidate patches and base-commit files.

Sources (all public, anonymous):
  * labels:   results/results.json of every evaluation/verified/* submission in
              github.com/SWE-bench/experiments at the pinned commit (common.LABELS_COMMIT)
  * patches:  <submission logs bucket>/<instance>/patch.diff, the bucket named by each
              submission's metadata.yaml `assets.logs`
  * apply:    the files a patch touches, at the instance's base commit, from the upstream repo

Everything is cached under common.WORK_DIR (git-ignored). No credential is used.

Usage:
  python fetch_patches.py pool                 # fetch/refresh the label pool index
  python fetch_patches.py select <instance>    # pick 3 resolved + 3 unresolved patches
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

UA = "failfirst-ext-research/1.0 (anonymous public-data fetch)"
RAW = "https://raw.githubusercontent.com"


def http_get(url: str, *, retries: int = 4, timeout: int = 60) -> bytes | None:
    """GET with backoff. Returns None on 404, raises after repeated other failures."""
    delay = 2.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404) and "s3.amazonaws.com" in url:
                return None          # S3 answers 403 for a missing key
            if exc.code == 404:
                return None
            if attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    return None


def cached_get(url: str, cache_path: Path) -> bytes | None:
    """Fetch once; a 404 is cached as a `.missing` marker so it is not retried."""
    missing = cache_path.with_name(cache_path.name + ".missing")
    if cache_path.exists():
        return cache_path.read_bytes()
    if missing.exists():
        return None
    data = http_get(url)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if data is None:
        missing.write_text("404\n", encoding="ascii")
        return None
    cache_path.write_bytes(data)
    return data


# --------------------------------------------------------------------------- pool

def _s3_https(s3_url: str) -> str:
    rest = s3_url[len("s3://"):]
    bucket, _, prefix = rest.partition("/")
    return f"https://{bucket}.s3.amazonaws.com/{prefix.rstrip('/')}"


#: results.json lists that mean the harness could not judge the patch fairly.
UNRELIABLE_LISTS = ("no_generation", "no_logs", "no_apply", "install_fail", "reset_failed",
                    "test_errored", "test_timeout")


def unresolved_set(res: dict, verified: set[str]) -> set[str]:
    """Label rule for 'unresolved' (pure; unit-tested)."""
    out = set(verified)
    if isinstance(res.get("generated"), list):
        out &= set(res["generated"])
    if isinstance(res.get("with_logs"), list):
        out &= set(res["with_logs"])
    for key in UNRELIABLE_LISTS:
        if isinstance(res.get(key), list):
            out -= set(res[key])
    return out - set(res.get("resolved") or [])


def list_submissions() -> list[str]:
    api = (f"https://api.github.com/repos/{C.LABELS_REPO}/contents/{C.LABELS_SUBDIR}"
           f"?ref={C.LABELS_COMMIT}")
    data = json.loads(http_get(api))
    return sorted(e["name"] for e in data if e.get("type") == "dir")


def fetch_pool(work: Path = C.WORK_DIR, refresh: bool = False) -> dict:
    """Index of the label pool at the pinned commit.

    {submission: {"logs": https-prefix, "results_sha256": ..., "resolved": [...],
                  "unresolved": [...]}}
    `unresolved` = Verified instances the submission produced a patch and logs for that the
    official harness did not mark resolved, excluding every harness-failure list present
    in that results.json (UNRELIABLE_LISTS). Two results.json layouts exist at the pinned
    commit; the rule reads whichever lists are present, so both are treated alike.
    """
    index_path = work / "pool" / "index.json"
    if index_path.exists() and not refresh:
        return json.loads(index_path.read_text(encoding="utf-8"))
    import yaml  # local dependency only; the box-side runner never needs it

    verified = set(C.read_lines(C.HERE / "verified_ids.txt"))
    pool = {}
    for sub in list_submissions():
        base = f"{RAW}/{C.LABELS_REPO}/{C.LABELS_COMMIT}/{C.LABELS_SUBDIR}/{sub}"
        res_raw = cached_get(f"{base}/results/results.json", work / "pool" / sub / "results.json")
        meta_raw = cached_get(f"{base}/metadata.yaml", work / "pool" / sub / "metadata.yaml")
        if not res_raw or not meta_raw:
            continue
        try:
            res = json.loads(res_raw)
            meta = yaml.safe_load(meta_raw) or {}
        except Exception:
            continue
        logs = ((meta.get("assets") or {}).get("logs") or "")
        if not isinstance(res.get("resolved"), list) or not str(logs).startswith("s3://"):
            continue
        resolved = sorted(set(res["resolved"]) & verified)
        unresolved = sorted(unresolved_set(res, verified))
        pool[sub] = {"logs": _s3_https(logs), "results_sha256": C.sha256_bytes(res_raw),
                     "layout": "legacy" if "applied" in res else "current",
                     "resolved": resolved, "unresolved": unresolved}
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(pool, indent=1, sort_keys=True), encoding="utf-8")
    return pool


def results_sha256(sub: str, work: Path = C.WORK_DIR) -> str | None:
    base = f"{RAW}/{C.LABELS_REPO}/{C.LABELS_COMMIT}/{C.LABELS_SUBDIR}/{sub}"
    raw = cached_get(f"{base}/results/results.json", work / "pool" / sub / "results.json")
    return C.sha256_bytes(raw) if raw else None


# --------------------------------------------------------------------------- patches

def fetch_patch(pool: dict, sub: str, instance_id: str, work: Path = C.WORK_DIR) -> str | None:
    url = f"{pool[sub]['logs']}/{instance_id}/patch.diff"
    data = cached_get(url, work / "patches" / sub / f"{instance_id}.diff")
    if data is None:
        return None
    return data.decode("utf-8", errors="replace")


def fetch_report(pool: dict, sub: str, instance_id: str, work: Path = C.WORK_DIR) -> dict | None:
    """The submission's own per-instance harness report, from the same logs bucket."""
    url = f"{pool[sub]['logs']}/{instance_id}/report.json"
    data = cached_get(url, work / "reports" / sub / f"{instance_id}.json")
    if data is None:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None


def unresolved_report_ok(report: dict | None, instance_id: str) -> bool:
    """Evidence that an 'unresolved' label is a real test failure, not a harness failure: the
    report exists, says the patch applied, carries tests_status, lists at least one
    FAIL_TO_PASS test, and records at least one passing test in FAIL_TO_PASS or PASS_TO_PASS
    (so the test suite demonstrably ran in a working environment). Pure; unit-tested."""
    r = (report or {}).get(instance_id)
    if not isinstance(r, dict) or r.get("patch_successfully_applied") is not True:
        return False
    ts = r.get("tests_status")
    if not isinstance(ts, dict):
        return False
    f2p = ts.get("FAIL_TO_PASS") or {}
    p2p = ts.get("PASS_TO_PASS") or {}
    if not (f2p.get("success") or f2p.get("failure")):
        return False
    return bool(f2p.get("success") or p2p.get("success"))


def patch_path(sub: str, instance_id: str, work: Path = C.WORK_DIR) -> Path:
    return work / "patches" / sub / f"{instance_id}.diff"


def _git() -> str:
    return shutil.which("git") or "git"


def git_apply_ok(patch: str, repo: str, base_commit: str, work: Path = C.WORK_DIR) -> tuple[bool, str]:
    """Does `git apply` accept the patch on the base commit? Only the touched files are
    materialised (fetched from the upstream repo at base_commit), in a temp dir that is
    outside any git repository."""
    tmp = Path(tempfile.mkdtemp(prefix="ffx_apply_"))
    try:
        for rel in C.patch_base_paths(patch):
            data = cached_get(f"{RAW}/{repo}/{base_commit}/{rel}",
                              work / "base" / repo.replace("/", "__") / base_commit / rel)
            if data is None:
                continue                      # absent at base: git apply will refuse
            dest = tmp / "tree" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        (tmp / "tree").mkdir(exist_ok=True)
        pfile = tmp / "p.diff"
        pfile.write_bytes(patch.encode("utf-8"))
        env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(tmp))
        proc = subprocess.run([_git(), "-c", "core.autocrlf=false", "apply", "--check", str(pfile)],
                              cwd=tmp / "tree", capture_output=True, text=True, env=env, timeout=120)
        return proc.returncode == 0, (proc.stderr or "").strip()[:200]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def candidate_order(pool: dict, instance_id: str, seed: int = C.SEED) -> list[tuple[str, str]]:
    """(submission, label) candidates for one instance, in the pre-registered hash order."""
    out = []
    for sub in sorted(pool, key=lambda s: C.submission_order_key(instance_id, s, seed)):
        e = pool[sub]
        if instance_id in e["resolved"]:
            out.append((sub, "resolved"))
        elif instance_id in e["unresolved"]:
            out.append((sub, "unresolved"))
    return out


def label_conflict_groups(pool: dict, iid: str, fetch, seed: int = C.SEED) -> list[dict]:
    """Scan EVERY labelled candidate of the instance (not just the ones a walk would reach) and
    return the identity groups whose members carry both published labels. Every member of such a
    group is ineligible: the same edit cannot be both a correct and an incorrect fix, so the
    labels of that edit are noise."""
    from concurrent.futures import ThreadPoolExecutor
    order = candidate_order(pool, iid, seed)
    with ThreadPoolExecutor(max_workers=8) as ex:      # fetch in parallel, group in order
        texts = list(ex.map(lambda c: fetch(c[0], iid), order))
    groups: dict[str, list] = {}
    for (sub, label), patch in zip(order, texts):
        if patch is None or not C.patch_is_nonempty(patch):
            continue
        groups.setdefault(C.patch_identity(patch), []).append({"submission": sub, "label": label})
    return [{"identity": ident, "members": members} for ident, members in sorted(groups.items())
            if len({m["label"] for m in members}) > 1]


def select_patches(pool: dict, inst: dict, work: Path = C.WORK_DIR, seed: int = C.SEED,
                   fetch=None, apply_ok=None, report_ok=None) -> dict:
    """Walk candidates in hash order; accept the first 3 resolved and 3 unresolved patches that
    are non-empty, not a member of a label-conflicting identity group, pairwise distinct after
    whitespace normalisation, (for unresolved) backed by harness-report evidence that the tests
    ran, and apply. Results per candidate: patch_unavailable | empty | label_conflict |
    duplicate | no_report_evidence | no_apply | accepted. `fetch`/`apply_ok`/`report_ok` are
    injectable for tests."""
    fetch = fetch or (lambda sub, iid: fetch_patch(pool, sub, iid, work))
    apply_ok = apply_ok or (lambda patch: git_apply_ok(patch, inst["repo"], inst["base_commit"], work))
    report_ok = report_ok or (lambda sub, iid: unresolved_report_ok(fetch_report(pool, sub, iid, work), iid))
    iid = inst["instance_id"]
    conflicts = label_conflict_groups(pool, iid, fetch, seed)
    conflict_idents = {g["identity"] for g in conflicts}
    need = {"resolved": C.N_RESOLVED, "unresolved": C.N_UNRESOLVED}
    chosen, tried, identities = [], [], {}
    for sub, label in candidate_order(pool, iid, seed):
        if need["resolved"] == 0 and need["unresolved"] == 0:
            break
        if need[label] == 0:
            continue
        patch = fetch(sub, iid)
        if patch is None:
            tried.append({"submission": sub, "label": label, "result": "patch_unavailable"})
            continue
        if not C.patch_is_nonempty(patch):
            tried.append({"submission": sub, "label": label, "result": "empty"})
            continue
        ident = C.patch_identity(patch)
        if ident in conflict_idents:
            tried.append({"submission": sub, "label": label, "result": "label_conflict"})
            continue
        if ident in identities:
            tried.append({"submission": sub, "label": label, "result": "duplicate",
                          "twin": identities[ident][0]})
            continue
        if label == "unresolved" and not report_ok(sub, iid):
            tried.append({"submission": sub, "label": label, "result": "no_report_evidence"})
            continue
        ok, why = apply_ok(patch)
        if not ok:
            tried.append({"submission": sub, "label": label, "result": "no_apply"})
            continue
        identities[ident] = (sub, label)
        need[label] -= 1
        tried.append({"submission": sub, "label": label, "result": "accepted"})
        chosen.append({"submission": sub, "label": label,
                       "patch_sha256": C.sha256_bytes(patch.encode("utf-8")),
                       "identity": ident})
    complete = need["resolved"] == 0 and need["unresolved"] == 0
    reason = None
    if not complete:
        reason = (f"insufficient eligible patches: resolved {C.N_RESOLVED - need['resolved']}/"
                  f"{C.N_RESOLVED}, unresolved {C.N_UNRESOLVED - need['unresolved']}/{C.N_UNRESOLVED}")
    return {"complete": complete, "reason": reason, "patches": chosen if complete else [],
            "tried": tried, "label_conflict_groups": conflicts}


def load_dataset(work: Path = C.WORK_DIR) -> dict:
    """{instance_id: row} from the pinned Verified parquet (downloaded once, hash-checked)."""
    path = work / "data" / "verified.parquet"
    if not path.exists():
        url = (f"https://huggingface.co/datasets/{C.DATASET_REPO}/resolve/"
               f"{C.DATASET_REVISION}/{C.DATASET_FILE}")
        data = http_get(url, timeout=300)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    digest = C.sha256_file(path)
    if digest != C.DATASET_SHA256:
        raise SystemExit(f"BLOCKED: dataset sha256 {digest} != pinned {C.DATASET_SHA256}")
    import pandas as pd
    df = pd.read_parquet(path)
    return {r["instance_id"]: r for r in df.to_dict("records")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pool")
    p.add_argument("--refresh", action="store_true")
    s = sub.add_parser("select")
    s.add_argument("instance_id")
    args = ap.parse_args(argv)
    pool = fetch_pool(refresh=getattr(args, "refresh", False))
    if args.cmd == "pool":
        n_leg = sum(1 for e in pool.values() if e["layout"] == "legacy")
        print(f"pool: {len(pool)} submissions with a resolved list and a logs bucket "
              f"({n_leg} legacy results layout)")
        return 0
    ds = load_dataset()
    res = select_patches(pool, ds[args.instance_id])
    print(json.dumps(res, indent=1))
    return 0 if res["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
