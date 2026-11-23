"""Synthetic end-to-end: fake run files -> analyze.run_full -> evidence JSON that satisfies the
shape the acceptance criteria C5-C9 assert (the numbers are synthetic, the plumbing is real)."""
import json
import random
from urllib.parse import urlparse

import analyze as A
import audit_oracle as AO
import common as C
import generate as G

N = 60


def _write_run(tmp_path, drop_one=False, models=("qwen3.7-plus",)):
    rng = random.Random(5)
    run = tmp_path / "run"
    (run / "checks").mkdir(parents=True)
    insts, checks, rows, gens = [], [], [], []
    for i in range(N):
        iid = f"repo__repo-{i}"
        patches = [{"submission": f"s{j}", "label": "resolved" if j < 3 else "unresolved",
                    "patch_sha256": f"{i:04d}{j}" + "0" * 59} for j in range(6)]
        insts.append({"instance_id": iid, "repo": "repo/repo", "patches": patches})
        for k in (1, 2, 3):
            cid = f"{iid}#{k}"
            csha = C.sha256_bytes(cid.encode())
            checks.append({"check_id": cid, "instance_id": iid, "k": k, "check_sha256": csha,
                           "path": f"checks/{iid}/check_{k}.py", "generation_failed": False})
            gens.append({"instance_id": iid, "k": k, "attempt": 0, "ok": True, "usable": True,
                         "script_sha256": csha, "returned_model": models[(i + k) % len(models)]})
            kind = rng.choice(["vac", "ff", "ff", "err"])
            unfixed_rc = {"vac": 0, "ff": 1, "err": 127}[kind]
            base = {"check_id": cid, "instance_id": iid, "check_sha256": csha, "timed_out": False,
                    "attempt": 1, "docker_rc": 0,
                    "assertion_error": kind == "ff", "started_utc": f"2026-11-24T0{k}:00:00+00:00"}
            for t in ("unfixed1", "unfixed2"):
                rows.append(dict(base, target=t, exit_code=unfixed_rc, applied=None, patch_sha256=None))
            for p in patches:
                if kind == "vac":
                    rc = 0
                elif kind == "ff":
                    rc = 0 if rng.random() < (0.7 if p["label"] == "resolved" else 0.15) else 1
                else:
                    rc = 127
                rows.append(dict(base, target="patch:" + p["submission"], exit_code=rc, applied=True,
                                 patch_sha256=p["patch_sha256"]))
            rows.append(dict(base, target="gold", exit_code=0 if kind != "err" else 127, applied=True,
                             patch_sha256="g"))
    if drop_one:
        rows.pop(5)
    lock = {"n_target": N, "n_skipped": 7, "n_walked": N + 7, "instances": insts}
    prompt_sha = C.sha256_file(C.HERE / "prompt.txt")
    manifest = {"prompt_sha256": prompt_sha, "endpoint_host": G.TOKEN_PLAN_HOST,
                "model_requested": G.MODEL, "params": G.PARAMS, "checks": checks}
    (run / "run_manifest.json").write_text(json.dumps(manifest))
    (run / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (run / "generations.jsonl").write_text("\n".join(json.dumps(g) for g in gens) + "\n")
    pairs = AO.select_pairs(insts)
    (run / "audit.json").write_text(json.dumps(AO.summarise([dict(p, rerun=p["label"], agree=True)
                                                               for p in pairs])))
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(lock))
    return run, lock_path


def test_evidence_shape_matches_acceptance_assertions(tmp_path, monkeypatch):
    run, lock_path = _write_run(tmp_path)
    out = tmp_path / "evidence.json"
    assert A.run_full(run, out, lock_path) == 0
    d = json.loads(out.read_text())
    # C5 (generator block; host compared with the module constant, not the policy file)
    g = d["generator"]
    assert g["endpoint_host"] == urlparse(G.BASE_URL).hostname
    assert isinstance(g["returned_models"], list) and len(set(g["returned_models"])) == 1
    assert g["n_generations"] == 3 * N
    # C6
    a, b, o = d["arms"]["unfiltered"], d["arms"]["failfirst"], d["unfixed_outcomes"]
    assert a["run_manifest_sha256"] == b["run_manifest_sha256"] and a["prompt_sha256"] == b["prompt_sha256"]
    assert a["n_checks"] == o["PASS"] + o["FAIL"] + o["ERROR"] and b["n_checks"] == o["FAIL"]
    assert b["n_green"] <= a["n_green"]
    # C7
    n = d["n_instances"]
    assert n == d["prereg_n"] and d["n_checks"] == 3 * n and d["n_pairs"] == 18 * n
    assert d["n_missing"] == 0 and d["n_skipped"] <= 0.2 * (n + d["n_skipped"])
    # C8 (audit shape)
    assert d["oracle"]["source_commit"] == C.LABELS_COMMIT and d["oracle"]["audit"]["n"] >= 1.2 * n
    # C9
    p = d["primary"]
    assert p["ci95"][0] <= p["delta_fgs"] <= p["ci95"][1]
    assert p["bootstrap_resamples"] == 10000 and p["cluster"] == "instance"
    assert len(d["placebo"]["ci95"]) == 2 and d["placebo"]["draws"] == 1000
    assert d["verdict"] in ("SUPPORTED", "AGAINST", "INCONCLUSIVE", "BLOCKED")
    assert "residual_false_green_rate" in d["secondary"] and "vacuous_share" in d["secondary"]
    assert d["first_sampled_run_utc"] == "2026-11-24T01:00:00+00:00"


def test_missing_verdict_and_two_models_block(tmp_path):
    run, lock_path = _write_run(tmp_path, drop_one=True, models=("qwen3.7-plus", "other"))
    out = tmp_path / "evidence.json"
    A.run_full(run, out, lock_path)
    d = json.loads(out.read_text())
    assert d["n_missing"] == 1 and d["verdict"] == "BLOCKED"
    assert any("missing" in f for f in d["integrity_failures"])
    assert any("distinct model" in f for f in d["integrity_failures"])
    assert len(d["generator"]["returned_models"]) == 2
