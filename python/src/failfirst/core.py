"""The two-phase protocol: baseline and verify (see spec/SPEC.md)."""
from __future__ import annotations

import datetime
import json
import os
from typing import Callable

from . import __version__
from .model import SPEC_VERSION, criterion_hash
from .runner import evaluate, observe as default_observe

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_REVIEW = 0, 1, 2, 3
DEFAULT_LOCK = ".failfirst.lock.json"

Observer = Callable[[dict], dict]


class LockError(Exception):
    """The lockfile is missing, unreadable, or would be overwritten.

    ``code`` is the stable error code: FF_E_LOCK_EXISTS, FF_E_NO_LOCK or FF_E_BAD_LOCK.
    """

    def __init__(self, message: str, code: str = "FF_E_BAD_LOCK") -> None:
        super().__init__(message)
        self.code = code


def _observer(observe: Observer | None, base_dir: str) -> Observer:
    return observe if observe is not None else (lambda c: default_observe(c, base_dir))


def baseline(criteria: list[dict], lock_path: str, observe: Observer | None = None,
             base_dir: str = ".", force: bool = False, dry_run: bool = False) -> tuple[dict, int]:
    """Run criteria against the current (unfixed) state and write the lockfile.

    With ``dry_run`` the criteria are run and reported but no lockfile is written.
    Returns (report, exit_code). Exit is 0 only if every non-judgment criterion FAILED
    (valid proof of a gap); passed ones are vacuous, errored ones are unusable.
    """
    if os.path.exists(lock_path) and not force:
        raise LockError(f"{lock_path} already exists; baseline would erase the failure evidence "
                        "(use --force to overwrite deliberately)", code="FF_E_LOCK_EXISTS")
    obs_fn = _observer(observe, base_dir)
    locked, rows = {}, []
    for c in criteria:
        entry = {"hash": criterion_hash(c), "judgment": c["judgment"]}
        if c["judgment"]:
            entry["baseline"] = {"status": "n/a", "detail": "judgment: awaiting human review"}
        else:
            entry["baseline"] = evaluate(c, obs_fn(c))
        locked[c["id"]] = entry
        rows.append({"id": c["id"], "statement": c["statement"], "judgment": c["judgment"],
                     "baseline": entry["baseline"]})
    lock = {"failfirst_lock": SPEC_VERSION, "created_at": datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "criteria": locked}
    if not dry_run:
        with open(lock_path, "w", encoding="utf-8") as fh:
            json.dump(lock, fh, indent=2, sort_keys=True)
            fh.write("\n")
    auto = [r for r in rows if not r["judgment"]]
    bad = [r for r in auto if r["baseline"]["status"] != "failed"]
    counts = {"failed": 0, "passed": 0, "error": 0, "judgment": len(rows) - len(auto)}
    for r in auto:
        counts[r["baseline"]["status"]] += 1
    code = EXIT_OK if auto and not bad else EXIT_FAIL
    report = {"tool": "failfirst", "version": __version__, "phase": "baseline",
              "status": "ok" if code == EXIT_OK else "warning", "exit_code": code,
              "summary": {"failed_as_required": counts["failed"],
                          "vacuous": counts["passed"], "errored": counts["error"],
                          "judgment": counts["judgment"]},
              "criteria": [dict(r, vacuous=(not r["judgment"] and r["baseline"]["status"] == "passed"))
                           for r in rows]}
    if dry_run:
        report["dry_run"] = True
    return report, code


def read_lock(lock_path: str) -> dict:
    try:
        with open(lock_path, "r", encoding="utf-8") as fh:
            lock = json.load(fh)
    except FileNotFoundError:
        raise LockError(f"no lockfile at {lock_path}; run `failfirst baseline` before the work",
                        code="FF_E_NO_LOCK") from None
    except (OSError, ValueError) as exc:
        raise LockError(f"cannot read lockfile {lock_path}: {exc}") from exc
    if not isinstance(lock, dict) or lock.get("failfirst_lock") != SPEC_VERSION \
            or not isinstance(lock.get("criteria"), dict):
        raise LockError(f"{lock_path} is not a failfirst v{SPEC_VERSION} lockfile")
    return lock


def verify(criteria: list[dict], lock_path: str, observe: Observer | None = None,
           base_dir: str = ".") -> tuple[dict, int]:
    """Re-run criteria; a criterion counts only if failed at baseline, unchanged, and passes now."""
    lock = read_lock(lock_path)
    locked = lock["criteria"]
    obs_fn = _observer(observe, base_dir)
    rows, current_ids = [], set()
    for c in criteria:
        current_ids.add(c["id"])
        base = locked.get(c["id"])
        row = {"id": c["id"], "statement": c["statement"], "judgment": c["judgment"]}
        if c["judgment"]:
            row.update(verdict="awaiting_review", reason="judgment criteria are never auto-passed")
        elif base is None:
            row.update(verdict="unbaselined", reason="not present at baseline; it never had a chance to fail")
        elif base["hash"] != criterion_hash(c):
            row.update(verdict="modified", reason="criterion changed since baseline; goalposts moved",
                       baseline=base["baseline"])
        elif base["judgment"]:
            row.update(verdict="modified", reason="was a judgment criterion at baseline")
        else:
            row["baseline"] = base["baseline"]
            bstat = base["baseline"]["status"]
            if bstat == "passed":
                row.update(verdict="vacuous", reason="already passed at baseline; carries no information")
            elif bstat == "error":
                row.update(verdict="baseline_error", reason="baseline run errored; failure was never demonstrated")
            else:
                now = evaluate(c, obs_fn(c))
                row["now"] = now
                if now["status"] == "passed":
                    row.update(verdict="proven", reason="failed at baseline, passes now, unchanged")
                elif now["status"] == "failed":
                    row.update(verdict="still_failing", reason=now["detail"])
                else:
                    row.update(verdict="error", reason=now["detail"])
        rows.append(row)
    for cid, base in locked.items():
        if cid not in current_ids:
            rows.append({"id": cid, "statement": "", "judgment": base["judgment"], "baseline": base["baseline"],
                         "verdict": "removed", "reason": "present at baseline but missing now"})
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    auto = [r for r in rows if r["verdict"] != "awaiting_review"]
    if not auto or any(r["verdict"] != "proven" for r in auto):
        status, code = "fail", EXIT_FAIL
    elif counts.get("awaiting_review"):
        status, code = "awaiting_review", EXIT_REVIEW
    else:
        status, code = "pass", EXIT_OK
    report = {"tool": "failfirst", "version": __version__, "phase": "verify", "status": status,
              "exit_code": code, "summary": counts, "criteria": rows}
    return report, code


def format_report(report: dict) -> str:
    """Human-readable summary of a baseline or verify report."""
    lines = []
    if report["phase"] == "baseline":
        lines.append("failfirst baseline")
        for r in report["criteria"]:
            if r["judgment"]:
                tag = "JUDGMENT "
            else:
                tag = {"failed": "FAILS ok ", "passed": "VACUOUS  ", "error": "ERROR    "}[r["baseline"]["status"]]
            lines.append(f"  {tag} {r['id']}: {r['statement'] or r['baseline']['detail']}")
        s = report["summary"]
        lines.append(f"{s['failed_as_required']} failed as required, {s['vacuous']} vacuous, "
                     f"{s['errored']} errored, {s['judgment']} awaiting judgment")
        if report["exit_code"]:
            lines.append("WARNING: some criteria did not fail at baseline; they will not count.")
    else:
        lines.append("failfirst verify")
        for r in report["criteria"]:
            lines.append(f"  {r['verdict'].upper():16} {r['id']}: {r['reason']}")
        summ = ", ".join(f"{n} {k}" for k, n in sorted(report["summary"].items()))
        lines.append(f"{summ}")
        lines.append({"pass": "PASS: every criterion was proven (failed first, passes now).",
                      "fail": "FAIL: not every criterion is proven.",
                      "awaiting_review": "AWAITING REVIEW: all machine checks proven; judgment criteria need a human."
                      }[report["status"]])
    return "\n".join(lines)
