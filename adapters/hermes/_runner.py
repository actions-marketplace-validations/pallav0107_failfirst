"""Locating and running the failfirst CLI, and building the gate command."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_NAMES = ("failfirst.json", "failfirst.yaml", "failfirst.yml")
LOCK_NAME = ".failfirst.lock.json"


def session_cwd() -> str:
    try:
        from agent.runtime_cwd import resolve_agent_cwd
        return str(resolve_agent_cwd())
    except Exception:  # noqa: BLE001 - any failure falls back to the process cwd
        return os.getcwd()


def find_failfirst() -> Optional[List[str]]:
    exe = shutil.which("failfirst")
    if exe:
        return [os.path.abspath(exe)]
    if importlib.util.find_spec("failfirst") is not None:
        return [sys.executable, "-m", "failfirst"]
    return None


def default_criteria(cwd: str) -> Optional[str]:
    for name in DEFAULT_NAMES:
        cand = os.path.join(cwd, name)
        if os.path.isfile(cand):
            return cand
    return None


def sha256_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_baseline(cli: List[str], criteria: str) -> Tuple[int, Dict[str, Any], str]:
    proc = subprocess.run(
        cli + ["baseline", criteria, "--json"], cwd=os.path.dirname(criteria),
        capture_output=True, text=True, timeout=600,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})  # no stale .pyc after a fast fix
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        report = {}
    return proc.returncode, report, (proc.stderr or proc.stdout).strip()


def bad_criteria(report: Dict[str, Any]) -> List[str]:
    """Describe each vacuous or errored criterion in a baseline report."""
    lines = []
    for item in report.get("criteria") or []:
        base = item.get("baseline") or {}
        if item.get("vacuous"):
            lines.append(f"- {item.get('id')}: vacuous (already passes on the unfixed code)")
        elif base.get("status") == "error":
            lines.append(f"- {item.get('id')}: errored ({base.get('detail', '')})")
    return lines


def gate_command(cli: List[str], criteria: str, lock: str, sha: str) -> str:
    """One POSIX command: lock hash pin, then failfirst verify.

    The hash check runs under this interpreter's absolute path (``python3`` may be absent), and the
    literals are JSON-encoded (valid Python, double-quoted) so the line stays readable when quoted.
    """
    prog = (f"import hashlib,sys;sys.exit(0 if hashlib.sha256("
            f"open({json.dumps(lock)},\"rb\").read()).hexdigest()=={json.dumps(sha)} else 1)")
    verify = "env PYTHONDONTWRITEBYTECODE=1 " + " ".join(shlex.quote(p) for p in cli) + (
        f" verify {shlex.quote(criteria)} --lock {shlex.quote(lock)} --quiet")
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(prog)} && {verify}"


def run_gate(command: str, cwd: str) -> Tuple[int, str]:
    proc = subprocess.run(command, shell=True, cwd=cwd, capture_output=True,
                          text=True, timeout=900)
    return proc.returncode, (proc.stdout + proc.stderr).strip()[-600:]
