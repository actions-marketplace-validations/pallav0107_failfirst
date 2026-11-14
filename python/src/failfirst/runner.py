"""Observation (running a check) and evaluation (judging an observation)."""
from __future__ import annotations

import os
import signal
import subprocess
import urllib.error
import urllib.request


def observe(criterion: dict, base_dir: str = ".") -> dict:
    """Run a criterion's check and return a raw observation (see spec/SPEC.md section 5)."""
    check = criterion["check"]
    kind = check["type"]
    if kind == "command":
        return _observe_command(check, base_dir)
    if kind == "file_contains":
        path = os.path.join(base_dir, check["path"])
        try:
            with open(path, "rb") as fh:
                return {"content": fh.read().decode("utf-8", "replace")}
        except FileNotFoundError:
            return {"missing": True}
        except OSError as exc:
            return {"error": f"cannot read file: {exc}"}
    return _observe_http(check)


def _observe_command(check: dict, base_dir: str) -> dict:
    cwd = os.path.join(base_dir, check["cwd"])
    posix = os.name == "posix"
    try:
        proc = subprocess.Popen(
            check["argv"] if "argv" in check else check["cmd"],
            shell="argv" not in check,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=posix,
        )
    except OSError as exc:
        return {"error": f"cannot start: {exc}"}
    try:
        out, err = proc.communicate(timeout=check["timeout"])
    except subprocess.TimeoutExpired:
        if posix:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        else:
            proc.kill()
        proc.communicate()
        return {"error": f"timeout after {check['timeout']}s"}
    text = out.decode("utf-8", "replace") + err.decode("utf-8", "replace")
    return {"exit": proc.returncode, "output": text}


def _observe_http(check: dict) -> dict:
    req = urllib.request.Request(check["url"], method=check["method"])
    try:
        with urllib.request.urlopen(req, timeout=check["timeout"]) as resp:
            return {"status": resp.status, "body": resp.read().decode("utf-8", "replace")}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read().decode("utf-8", "replace")}
    except Exception as exc:  # noqa: BLE001 - network failure is an error, not a pass/fail
        return {"error": f"request failed: {exc}"}


def _text_checks(check: dict, text: str) -> str | None:
    for s in check["expect_contains"]:
        if s not in text:
            return f"output missing expected text {s!r}"
    for s in check["expect_not_contains"]:
        if s in text:
            return f"output contains forbidden text {s!r}"
    return None


def evaluate(criterion: dict, obs: dict) -> dict:
    """Turn an observation into {"status": passed|failed|error, "detail": str}."""
    check = criterion["check"]
    if "error" in obs:
        return {"status": "error", "detail": str(obs["error"])}
    kind = check["type"]
    if kind == "command":
        if obs["exit"] != check["expect_exit"]:
            return {"status": "failed", "detail": f"exit {obs['exit']}, expected {check['expect_exit']}"}
        problem = _text_checks(check, obs.get("output", ""))
    elif kind == "file_contains":
        if obs.get("missing"):
            return {"status": "failed", "detail": "file does not exist"}
        problem = _text_checks(check, obs.get("content", ""))
    else:
        if obs["status"] != check["expect_status"]:
            return {"status": "failed", "detail": f"status {obs['status']}, expected {check['expect_status']}"}
        problem = _text_checks(check, obs.get("body", ""))
    if problem:
        return {"status": "failed", "detail": problem}
    return {"status": "passed", "detail": "ok"}
