"""Shared constants and pure helpers for the fail-first SWE-bench Verified experiment.

Everything here is deterministic and side-effect free so that the unit tests can pin it.
Nothing in this module touches the network, Docker or a credential.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
#: Working/cache directory for downloaded public material and run outputs. It is
#: git-ignored (build/) and deliberately OUTSIDE this directory, so third-party patches,
#: generated scripts and upstream metadata never sit in the experiment's code tree.
WORK_DIR = REPO_ROOT / "build" / "failfirst_ext"

TASK_ID = "failfirst-swebench-indep"
SEED = 20261123
N_TARGET = 100
K_CHECKS = 3
N_RESOLVED = 3
N_UNRESOLVED = 3
CHECK_TIMEOUT_S = 120

DATASET_REPO = "princeton-nlp/SWE-bench_Verified"
DATASET_REVISION = "c104f840cc67f8b6eec6f759ebc8b2693d585d4a"
DATASET_FILE = "data/test-00000-of-00001.parquet"
DATASET_SHA256 = "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd"

LABELS_REPO = "SWE-bench/experiments"
LABELS_COMMIT = "40f164d5b8f1d249bf95a6df8b74b577fd8e519d"
LABELS_SUBDIR = "evaluation/verified"

PASS, FAIL, ERROR = "PASS", "FAIL", "ERROR"
#: Not an outcome: the run produced no verdict (no exit code, docker error, patch did not
#: apply in the container, outer timeout). Missing rows are retried once and never classified.
MISSING = "MISSING"
#: Exit codes that mean "the check could not run", not "the behaviour is wrong".
#: 124/137 are what `timeout -k` returns when it has to stop the script.
ERROR_EXIT_CODES = frozenset({124, 126, 127, 137})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def image_name(instance_id: str) -> str:
    """Public SWE-bench instance image on Docker Hub (x86_64)."""
    return "swebench/sweb.eval.x86_64." + instance_id.replace("__", "_1776_").lower() + ":latest"


def instance_from_image(image: str) -> str:
    name = image.split("/", 1)[-1].split(":", 1)[0]
    name = name[len("sweb.eval.x86_64."):] if name.startswith("sweb.eval.x86_64.") else name
    return name.replace("_1776_", "__")


# --------------------------------------------------------------------------- outcomes

def classify_run(exit_code: int | None, timed_out: bool = False) -> str:
    """The exit-code rule of the published tool: 0 = PASS; 126/127 or a timeout = ERROR;
    any other non-zero exit = FAIL. No exit code at all is MISSING (infrastructure), not ERROR."""
    if exit_code is None:
        return MISSING
    if timed_out:
        return ERROR
    if exit_code == 0:
        return PASS
    if exit_code in ERROR_EXIT_CODES:
        return ERROR
    return FAIL


def row_completed(row: dict) -> bool:
    """Did this execution row produce a verdict? Recomputed from the raw fields, never from a
    stored status: an exit code was read from the in-container marker, docker itself exited 0,
    the outer watchdog did not fire, and (for a patched tree) the patch applied in the container.
    A timeout inside the container (124/137) IS a completed run with outcome ERROR."""
    if row.get("exit_code") is None or row.get("docker_rc") != 0 or row.get("outer_timeout"):
        return False
    if row.get("patch_sha256") is not None and row.get("applied") is not True:
        return False
    return True


def combine_unfixed(first: str, second: str) -> str:
    """Two runs on the unfixed tree. Disagreement (flaky) is ERROR, so is any ERROR."""
    if ERROR in (first, second) or first != second:
        return ERROR
    return first


def is_green(patched_outcome: str, applied: bool = True) -> bool:
    """green(check, patch) = PASS on the patched tree. A patch that does not apply is never green."""
    return bool(applied) and patched_outcome == PASS


def in_failfirst_arm(unfixed_outcome: str) -> bool:
    """Arm-B membership. A pure function of the unfixed outcome and nothing else:
    it never sees labels, patch outcomes or the check text."""
    return unfixed_outcome == FAIL


# --------------------------------------------------------------------------- patches

_DIFF_GIT = re.compile(r"^diff --git a/(\S+) b/(\S+)")


def patch_change_lines(patch: str) -> list[str]:
    out = []
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            out.append(line)
    return out


def normalise_patch(patch: str) -> str:
    """Whitespace-insensitive identity of a patch: the touched file names plus every
    added/removed line with ALL whitespace removed. Index lines, hunk offsets and
    context lines do not take part, so two submissions that make the same edit
    against slightly different context count as the same patch."""
    files = []
    for line in patch.splitlines():
        m = _DIFF_GIT.match(line)
        if m:
            files.append(m.group(2))
    body = ["".join(line.split()) for line in patch_change_lines(patch)]
    body = [b for b in body if b not in ("+", "-")]
    return "\n".join(["F:" + f for f in files] + body)


def patch_identity(patch: str) -> str:
    return sha256_bytes(normalise_patch(patch).encode("utf-8"))


def patch_is_nonempty(patch: str) -> bool:
    return any(len("".join(line[1:].split())) > 0 for line in patch_change_lines(patch))


def patch_base_paths(patch: str) -> list[str]:
    """Files that must exist at the base commit for the patch to apply."""
    paths = []
    for line in patch.splitlines():
        if line.startswith("--- a/"):
            paths.append(line[6:].split("\t", 1)[0].strip())
        elif line.startswith("rename from ") or line.startswith("copy from "):
            paths.append(line.split(" from ", 1)[1].strip())
    seen, out = set(), []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def submission_order_key(instance_id: str, submission: str, seed: int = SEED) -> str:
    return sha256_bytes(f"{seed}:{instance_id}:{submission}".encode("utf-8"))


# --------------------------------------------------------------------------- freeze

FREEZE_FILE = "PREREG.sha256"
_FREEZE_SKIP_DIRS = {"__pycache__", ".pytest_cache"}
#: The two files the acceptance check C2 names explicitly; the freeze must always cover them.
FREEZE_REQUIRED = ("PREREG.md", "prompt.txt")


def frozen_listing(base: Path) -> list[str]:
    """Every file in the experiment folder (posix relative paths), except caches and the hash
    file itself. Code, tests, box scripts, the lock, the id lists, the prompt and the prereg."""
    base = Path(base)
    out = []
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base)
        if not p.is_file() or any(part in _FREEZE_SKIP_DIRS for part in rel.parts):
            continue
        if rel.suffix == ".pyc" or rel.as_posix() == FREEZE_FILE:
            continue
        out.append(rel.as_posix())
    return out


def read_freeze(base: Path) -> dict[str, str] | None:
    path = Path(base) / FREEZE_FILE
    if not path.exists():
        return None
    want = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "  " in line:
            digest, name = line.split("  ", 1)
            want[name.strip().lstrip("*")] = digest.strip().lower()
    return want


def prereg_gate(base: Path, require_frozen: bool = True) -> tuple[bool, str]:
    """(ok, message). When PREREG.sha256 exists, EVERY file of the folder must match it and no
    unfrozen file may exist; this holds in every mode. When it does not exist, only callers that
    pass require_frozen=False (pilot work before the freeze) may proceed."""
    want = read_freeze(base)
    if want is None:
        if require_frozen:
            return False, "BLOCKED: prereg not frozen (PREREG.sha256 missing)"
        return True, "prereg not frozen yet (pilot mode only)"
    for name in FREEZE_REQUIRED:
        if name not in want:
            return False, f"BLOCKED: prereg hash file does not cover {name}"
    present = set(frozen_listing(base))
    for name in sorted(set(want) - present):
        return False, f"BLOCKED: prereg hash: frozen file {name} is missing"
    for name in sorted(present - set(want)):
        return False, f"BLOCKED: prereg hash: {name} is not in the freeze"
    for name in sorted(want):
        got = sha256_file(Path(base) / name)
        if got != want[name]:
            return False, f"BLOCKED: prereg hash mismatch for {name} ({got[:12]} != {want[name][:12]})"
    return True, "prereg hash OK (all frozen files match)"


def lock_gate(base: Path, lock_path: Path | str) -> tuple[bool, str]:
    """A sampled run may only use the frozen sample.lock.json, byte for byte."""
    want = (read_freeze(base) or {}).get("sample.lock.json")
    if want is None:
        return False, "BLOCKED: lock: no frozen sample.lock.json"
    got = sha256_file(lock_path)
    if got != want:
        return False, f"BLOCKED: lock {lock_path} differs from the frozen sample.lock.json"
    return True, "lock matches the freeze"


def read_lines(path: Path) -> list[str]:
    return [ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
