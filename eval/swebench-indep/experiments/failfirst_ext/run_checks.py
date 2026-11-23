"""Windows-side orchestration of check execution on the Docker host.

Only generated check files, public patches and the box runner travel to the host. The
host name is never stored in this repository: pass --host or set FFX_HOST.

  python run_checks.py select-pilot --run-dir DIR ID [ID ...]   # 3+3 patches for pilot ids
      [--unfixed-gold-only]                                      # pilot rule: no candidate patches
  python run_checks.py bundle --run-dir DIR [--lock sample.lock.json]
  python run_checks.py push   --run-dir DIR --host H [--remote-dir failfirst_ext/run_x]
  python run_checks.py start  --run-dir DIR --host H [--remote-dir ...]   # nohup on the host
  python run_checks.py fetch  --run-dir DIR --host H [--remote-dir ...]   # results.jsonl back

Per check the tasks are: unfixed1, unfixed2 (flakiness), patch:<submission> x 6, gold.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

TARGETS_UNFIXED = ("unfixed1", "unfixed2")


def build_tasks(manifest: dict, instances: list[dict]) -> list[dict]:
    """Pure: the full task list for a run (unit-tested)."""
    by_iid = {i["instance_id"]: i for i in instances}
    tasks = []
    for c in sorted(manifest["checks"], key=lambda c: c["check_id"]):
        inst = by_iid[c["instance_id"]]
        base = {"check_id": c["check_id"], "instance_id": c["instance_id"],
                "image": C.image_name(c["instance_id"]), "check": c["path"]}
        for t in TARGETS_UNFIXED:
            tasks.append(dict(base, target=t, patch=None))
        for p in inst["patches"]:
            tasks.append(dict(base, target="patch:" + p["submission"],
                              patch=f"patches/{c['instance_id']}/{p['submission']}.diff"))
        tasks.append(dict(base, target="gold", patch=f"patches/{c['instance_id']}/gold.diff"))
    return tasks


def cmd_select_pilot(args) -> int:
    import fetch_patches as F
    pilot = set(C.read_lines(C.HERE / "pilot_ids.txt"))
    bad = [i for i in args.ids if i not in pilot]
    if bad:
        print(f"BLOCKED: not pilot ids: {bad}")
        return 2
    pool, ds = F.fetch_pool(), F.load_dataset()
    out = []
    for iid in args.ids:
        row = ds[iid]
        if args.unfixed_gold_only:      # the registered pilot rule needs only unfixed + gold runs
            res = {"complete": True, "reason": None, "patches": [], "tried": []}
        else:
            res = F.select_patches(pool, row)
        print(f"{iid}: complete={res['complete']} {res['reason'] or ''}")
        out.append({"instance_id": iid, "repo": row["repo"], "version": str(row["version"]),
                    "base_commit": row["base_commit"], "image": C.image_name(iid),
                    "patches": res["patches"], "complete": res["complete"], "tried": res["tried"]})
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pilot_patches.json").write_text(json.dumps({"instances": out}, indent=1), encoding="utf-8")
    return 0


def cmd_bundle(args) -> int:
    import fetch_patches as F
    run_dir = Path(args.run_dir)
    pilot = set(C.read_lines(C.HERE / "pilot_ids.txt"))
    ok, msg = C.prereg_gate(C.HERE, require_frozen=bool(args.lock))
    if not ok:
        print(msg + " -- refusing to bundle")
        return 3
    if args.lock:
        ok, msg = C.lock_gate(C.HERE, args.lock)
        if not ok:
            print(msg)
            return 3
        instances = json.loads(Path(args.lock).read_text(encoding="utf-8"))["instances"]
    else:
        instances = json.loads((run_dir / "pilot_patches.json").read_text(encoding="utf-8"))["instances"]
        if any(i["instance_id"] not in pilot for i in instances):
            print("BLOCKED: pilot bundle contains non-pilot ids")
            return 2
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    pool, ds = F.fetch_pool(), F.load_dataset()
    bundle = run_dir / "bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    for c in manifest["checks"]:
        dest = bundle / c["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run_dir / c["path"], dest)
    for inst in instances:
        iid = inst["instance_id"]
        pdir = bundle / "patches" / iid
        pdir.mkdir(parents=True, exist_ok=True)
        for p in inst["patches"]:
            text = F.fetch_patch(pool, p["submission"], iid)
            assert C.sha256_bytes(text.encode("utf-8")) == p["patch_sha256"], (iid, p["submission"])
            (pdir / f"{p['submission']}.diff").write_bytes(text.encode("utf-8"))
        (pdir / "gold.diff").write_bytes(str(ds[iid]["patch"]).encode("utf-8"))
    tasks = build_tasks(manifest, instances)
    (bundle / "tasks.json").write_text(json.dumps({"tasks": tasks}, indent=1), encoding="utf-8", newline="\n")
    shutil.copyfile(C.HERE / "box" / "box_runner.py", bundle / "box_runner.py")
    print(f"bundle: {len(manifest['checks'])} checks, {len(tasks)} tasks -> {bundle}")
    return 0


def _host(args) -> str:
    h = args.host or os.environ.get("FFX_HOST")
    if not h:
        raise SystemExit("pass --host or set FFX_HOST")
    return h


def _remote(args) -> str:
    return args.remote_dir or f"failfirst_ext/{Path(args.run_dir).name}"


def cmd_push(args) -> int:
    host, remote = _host(args), _remote(args)
    subprocess.run(["ssh", host, f"mkdir -p {remote}"], check=True)
    bundle = Path(args.run_dir) / "bundle"
    subprocess.run(["scp", "-q", "-r"] + [str(p) for p in bundle.iterdir()] + [f"{host}:{remote}/"],
                   check=True)
    print(f"pushed {bundle} -> {host}:{remote}")
    return 0


def cmd_start(args) -> int:
    host, remote = _host(args), _remote(args)
    cmd = (f"cd {remote} && nohup setsid python3 box_runner.py --bundle . --workers {args.workers} "
           f"> runner.log 2>&1 < /dev/null & echo started")
    subprocess.run(["ssh", "-f", host, cmd], check=True)
    return 0


def cmd_fetch(args) -> int:
    host, remote = _host(args), _remote(args)
    dest = Path(args.run_dir)
    subprocess.run(["scp", "-q", f"{host}:{remote}/results.jsonl", str(dest / "results.jsonl")], check=True)
    n = sum(1 for ln in (dest / "results.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip())
    print(f"fetched {n} rows")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("select-pilot", "bundle", "push", "start", "fetch"):
        p = sp.add_parser(name)
        p.add_argument("--run-dir", required=True)
        p.add_argument("--host")
        p.add_argument("--remote-dir")
        p.add_argument("--workers", type=int, default=6)
        if name == "select-pilot":
            p.add_argument("ids", nargs="+")
            p.add_argument("--unfixed-gold-only", action="store_true")
        if name == "bundle":
            p.add_argument("--lock")
    args = ap.parse_args(argv)
    return {"select-pilot": cmd_select_pilot, "bundle": cmd_bundle, "push": cmd_push,
            "start": cmd_start, "fetch": cmd_fetch}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
