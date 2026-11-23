"""Prereg hash gate, sample verification, generator safety rails and the box runner's parsing."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import analyze as A
import box_runner as BR
import common as C
import generate as G
import run_checks as RC
import sample as S

EXP = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ prereg gate (C10 logic)

def _copy_with_freeze(tmp_path: Path, freeze: bool = True) -> Path:
    dst = tmp_path / "exp"
    shutil.copytree(EXP, dst, ignore=shutil.ignore_patterns("__pycache__", "tests", ".pytest_cache",
                                                            "PREREG.sha256"))
    if freeze:
        import freeze as FZ
        FZ.write_manifest(dst)
    return dst


def _dry(dst: Path):
    p = subprocess.run([sys.executable, str(dst / "analyze.py"), "--dry-run"], capture_output=True,
                       text=True, cwd=str(dst.parent))
    return p.returncode, p.stdout + p.stderr


def test_gate_accepts_untampered_copy(tmp_path):
    rc, out = _dry(_copy_with_freeze(tmp_path))
    assert "BLOCKED: prereg hash" not in out
    assert rc == 0 and "DRY RUN OK" in out


@pytest.mark.parametrize("victim", ["PREREG.md", "prompt.txt"])
def test_gate_refuses_tampered_copy(tmp_path, victim):
    dst = _copy_with_freeze(tmp_path)
    with (dst / victim).open("ab") as fh:
        fh.write(b"tamper\n")
    rc, out = _dry(dst)
    assert "BLOCKED: prereg hash" in out
    assert rc != 0


def test_gate_refuses_whitespace_only_change(tmp_path):
    dst = _copy_with_freeze(tmp_path)
    data = (dst / "PREREG.md").read_bytes()
    (dst / "PREREG.md").write_bytes(data.replace(b"\n", b"\r\n", 1))
    rc, out = _dry(dst)
    assert "BLOCKED: prereg hash" in out and rc != 0


def test_gate_refuses_when_not_frozen(tmp_path):
    rc, out = _dry(_copy_with_freeze(tmp_path, freeze=False))
    assert rc != 0 and "BLOCKED: prereg not frozen" in out


def test_generate_refuses_non_pilot_ids_and_unfrozen_sampled_run(tmp_path):
    assert G.main(["--pilot", "astropy__astropy-12907", "--run-dir", str(tmp_path / "r")]) == 2
    if not (EXP / "PREREG.sha256").exists():
        assert G.main(["--lock", str(EXP / "sample.lock.json"), "--run-dir", str(tmp_path / "r")]) == 3


# ------------------------------------------------------------------ sample

def test_frame_order_is_seeded_and_excludes_pilot():
    verified, pilot = S.load_frame_files()
    o1 = S.frame_order(C.SEED, verified, pilot)
    assert o1 == S.frame_order(C.SEED, verified, pilot)
    assert o1 != S.frame_order(C.SEED + 1, verified, pilot)
    assert len(o1) == len(verified) - len(pilot) == 478
    assert not set(o1) & set(pilot)


def _fake_pool():
    subs = [f"sub{i:02d}" for i in range(12)]
    return {s: {"resolved": ["x__x-1"] if i % 2 else [], "unresolved": [] if i % 2 else ["x__x-1"],
                "logs": "https://example.invalid", "results_sha256": "0"} for i, s in enumerate(subs)}


def test_select_patches_rule_order_distinct_and_apply():
    import fetch_patches as F
    pool = _fake_pool()
    order = F.candidate_order(pool, "x__x-1")
    patches = {s: f"diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+v_{s} = 1\n"
               for s in pool}
    first_sub, first_label = order[0]
    twin = next(s for s, lab in order[1:] if lab == first_label)       # same label, later in order
    patches[twin] = patches[first_sub].replace("= 1", "  =   1")         # whitespace-only twin
    no_apply = next(s for s, lab in order[1:] if lab != first_label)
    res = F.select_patches(pool, {"instance_id": "x__x-1", "repo": "r", "base_commit": "c"},
                           fetch=lambda s, i: patches[s],
                           apply_ok=lambda p: (p is not patches[no_apply], ""),
                           report_ok=lambda s, i: True)
    assert res["complete"]
    by_sub = {t["submission"]: t["result"] for t in res["tried"]}
    assert by_sub[twin] == "duplicate" and by_sub[no_apply] == "no_apply"
    assert [(t["submission"], t["label"]) for t in res["tried"]] == order[:len(res["tried"])]
    assert sum(p["label"] == "resolved" for p in res["patches"]) == 3
    assert len({p["identity"] for p in res["patches"]}) == 6


def test_normalise_patch_whitespace_insensitive_but_content_sensitive():
    a = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,2 @@\n ctx\n-x = 1\n+x = 2\n"
    b = "diff --git a/f.py b/f.py\nindex 1..2\n--- a/f.py\n+++ b/f.py\n@@ -5,2 +5,2 @@\n other\n-x=1\n+x  =  2\n"
    c = a.replace("x = 2", "x = 3")
    assert C.patch_identity(a) == C.patch_identity(b)
    assert C.patch_identity(a) != C.patch_identity(c)
    assert not C.patch_is_nonempty("diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-\n+  \n")


def test_unresolved_label_rule_excludes_harness_failures():
    import fetch_patches as F
    verified = {"a", "b", "c", "d", "e"}
    current = {"no_generation": ["a"], "no_logs": ["b"], "resolved": ["c"]}
    assert F.unresolved_set(current, verified) == {"d", "e"}
    legacy = {"generated": ["b", "c", "d", "e"], "with_logs": ["c", "d", "e"], "no_apply": ["d"],
              "resolved": ["c"], "applied": ["c", "e"]}
    assert F.unresolved_set(legacy, verified) == {"e"}


@pytest.mark.skipif(not (EXP / "sample.lock.json").exists(), reason="no lock yet")
def test_verify_detects_tampered_lock():
    import copy
    import fetch_patches as F
    lock = json.loads((EXP / "sample.lock.json").read_text(encoding="utf-8"))
    pool = F.fetch_pool()
    assert S.verify(lock, C.SEED, pool=pool) == (100, 0, 600)
    bad = copy.deepcopy(lock)
    bad["walk"][0], bad["walk"][1] = bad["walk"][1], bad["walk"][0]
    with pytest.raises(S.VerifyError):
        S.verify(bad, C.SEED, pool=pool)
    bad = copy.deepcopy(lock)
    bad["instances"][0]["patches"][0]["label"] = "unresolved"
    with pytest.raises(S.VerifyError):
        S.verify(bad, C.SEED, pool=pool)
    with pytest.raises(S.VerifyError):
        S.verify(lock, C.SEED + 1, pool=pool)


# ------------------------------------------------------------------ generator safety rails

def _fake(prefix):
    return prefix + "X" * 40


def test_prepaid_key_only(tmp_path, monkeypatch):
    for n in G.KEY_NAMES + ("paygqwen",):
        monkeypatch.delenv(n, raising=False)
    env = tmp_path / ".env"
    env.write_text("paygqwen=" + _fake("sk" + "-") + "\n", encoding="utf-8")
    key, why = G.prepaid_key(env)
    assert key is None and "no prepaid" in why               # metered key never returned
    env.write_text("qwen=" + _fake("sk" + "-") + "\n", encoding="utf-8")
    assert G.prepaid_key(env)[0] is None                     # wrong shape under the right name
    env.write_text("paygqwen=" + _fake("sk" + "-") + "\nqwen=" + _fake(G.PREPAID_PREFIX) + "\n",
                   encoding="utf-8")
    key, src = G.prepaid_key(env)
    assert key.startswith(G.PREPAID_PREFIX) and src == "qwen"


def test_egress_only_token_plan_host():
    assert G.egress_ok(G.BASE_URL + "/chat/completions")
    assert not G.egress_ok("https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    assert not G.egress_ok("http://" + G.TOKEN_PLAN_HOST + "/v1")
    assert not G.egress_ok("https://" + G.TOKEN_PLAN_HOST + ".evil.example/v1")


def test_extract_script():
    assert G.extract_script("```python\nimport sys\nsys.exit(0)\n```") == "import sys\nsys.exit(0)\n"
    assert G.extract_script("x = 1\n") == "x = 1\n"
    assert G.extract_script("Sure! here: ```python\ndef (:\n```") is None
    assert G.extract_script("") is None


def test_regeneration_seeds_and_stub(tmp_path):
    calls = []

    def caller(key, prompt, seed):
        calls.append(seed)
        return {"ok": True, "text": "no code here (", "returned_model": "m"}
    rows = []
    inst = {"instance_id": "x__x-1", "repo": "r", "version": "1", "problem_statement": "p"}
    c = G.generate_slot("SECRETKEYVALUE", "{{REPO}} {{VERSION}} {{PROBLEM_STATEMENT}}", inst, 2, tmp_path, rows.append, caller)
    assert calls == [2, 201, 202]
    assert c["generation_failed"] and c["attempts"] == 3
    assert (tmp_path / "x__x-1" / "check_2.py").read_text() == G.STUB
    assert "SECRETKEYVALUE" not in json.dumps(rows)                       # key never logged
    assert C.classify_run(127) == C.ERROR                                 # the stub is an ERROR


def test_prompt_placeholders_and_render():
    tpl = (EXP / "prompt.txt").read_text(encoding="utf-8")
    for ph in ("{{REPO}}", "{{VERSION}}", "{{PROBLEM_STATEMENT}}"):
        assert tpl.count(ph) == 1
    out = G.render_prompt(tpl, {"repo": "a/b", "version": "1.0", "problem_statement": "uses {{VERSION}}"})
    assert "a/b" in out and "uses {{VERSION}}" in out


# ------------------------------------------------------------------ runner

def test_runner_markers_and_exceptions():
    out = "hello FFX_abc_RC=0 fake\nFFX_n1_APPLY=0\nprint\nFFX_n1_RC=3\n"
    assert BR.parse_markers(out, "n1") == (3, True)
    assert BR.parse_markers("FFX_n1_APPLY=1\n", "n1") == (None, False)
    tb = "Traceback (most recent call last):\n  File x\nAssertionError: boom\n"
    assert BR.exception_type(tb) == "AssertionError"
    assert BR.exception_type("plain stderr\n") is None
    s = BR.container_script("n1", 120, with_patch=True)
    assert "timeout -k 5 120 python /ffx/check.py" in s and "git apply /ffx/patch.diff" in s
    cmd = BR.docker_cmd("ffx_n1", "img", Path("/c.py"), None, "true")
    assert ["--network", "none"] == cmd[cmd.index("--network"):cmd.index("--network") + 2]
    assert "never" == cmd[cmd.index("--pull") + 1]


def test_task_list_shape():
    manifest = {"checks": [{"check_id": f"x__x-1#{k}", "instance_id": "x__x-1", "k": k,
                            "path": f"checks/x__x-1/check_{k}.py"} for k in (1, 2, 3)]}
    insts = [{"instance_id": "x__x-1", "patches": [{"submission": f"s{i}"} for i in range(6)]}]
    tasks = RC.build_tasks(manifest, insts)
    assert len(tasks) == 3 * (2 + 6 + 1)
    assert sum(t["target"].startswith("patch:") for t in tasks) == 18
