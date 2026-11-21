// The two-phase protocol: baseline and verify (see spec/SPEC.md).
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { criterionHash, SPEC_VERSION, type Criterion } from "./model.js";
import { evaluate, observe as defaultObserve, type Evaluation, type Observation } from "./runner.js";

export const VERSION = "0.1.1";
export const EXIT_OK = 0, EXIT_FAIL = 1, EXIT_USAGE = 2, EXIT_REVIEW = 3;
export const DEFAULT_LOCK = ".failfirst.lock.json";

/** The lockfile is missing, unreadable or would be overwritten. `code` is FF_E_LOCK_EXISTS, FF_E_NO_LOCK or FF_E_BAD_LOCK. */
export class LockError extends Error {
  readonly code: string;
  constructor(message: string, code = "FF_E_BAD_LOCK") {
    super(message);
    this.code = code;
  }
}

export type Observer = (c: Criterion) => Observation | Promise<Observation>;

export interface Report {
  tool: "failfirst";
  version: string;
  phase: "baseline" | "verify";
  status: string;
  exit_code: number;
  summary: Record<string, number>;
  criteria: Array<Record<string, unknown> & { id: string; verdict?: string }>;
  /** Present (true) only for `baseline` with dryRun: nothing was written. */
  dry_run?: true;
}

interface LockEntry {
  hash: string;
  judgment: boolean;
  baseline: Evaluation | { status: "n/a"; detail: string };
}
interface Lock {
  failfirst_lock: number;
  created_at: string;
  criteria: Record<string, LockEntry>;
}

export interface Options {
  observe?: Observer;
  baseDir?: string;
}

export async function baseline(
  criteria: Criterion[],
  lockPath: string,
  opts: Options & { force?: boolean; dryRun?: boolean } = {},
): Promise<[Report, number]> {
  if (existsSync(lockPath) && !opts.force)
    throw new LockError(`${lockPath} already exists; baseline would erase the failure evidence (use --force to overwrite deliberately)`, "FF_E_LOCK_EXISTS");
  const obs = opts.observe ?? ((c) => defaultObserve(c, opts.baseDir ?? "."));
  const locked: Record<string, LockEntry> = {};
  const rows: Array<Record<string, unknown>> = [];
  for (const c of criteria) {
    const base = c.judgment
      ? { status: "n/a" as const, detail: "judgment: awaiting human review" }
      : evaluate(c, await obs(c));
    locked[c.id] = { hash: criterionHash(c), judgment: c.judgment, baseline: base };
    rows.push({ id: c.id, statement: c.statement, judgment: c.judgment, baseline: base, vacuous: !c.judgment && base.status === "passed" });
  }
  const lock: Lock = { failfirst_lock: SPEC_VERSION, created_at: new Date().toISOString().replace(/\.\d+Z$/, "Z"), criteria: locked };
  if (!opts.dryRun) writeFileSync(lockPath, JSON.stringify(sortDeep(lock), null, 2) + "\n");
  const auto = rows.filter((r) => !r.judgment);
  const n = (s: string) => auto.filter((r) => (r.baseline as Evaluation).status === s).length;
  const code = auto.length && n("failed") === auto.length ? EXIT_OK : EXIT_FAIL;
  const report: Report = {
    tool: "failfirst", version: VERSION, phase: "baseline", status: code === EXIT_OK ? "ok" : "warning", exit_code: code,
    summary: { failed_as_required: n("failed"), vacuous: n("passed"), errored: n("error"), judgment: rows.length - auto.length },
    criteria: rows as Report["criteria"],
  };
  if (opts.dryRun) report.dry_run = true;
  return [report, code];
}

function sortDeep(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (v && typeof v === "object") {
    const o: Record<string, unknown> = {};
    for (const k of Object.keys(v).sort()) o[k] = sortDeep((v as Record<string, unknown>)[k]);
    return o;
  }
  return v;
}

export function readLock(lockPath: string): Lock {
  let lock: Lock;
  try {
    lock = JSON.parse(readFileSync(lockPath, "utf8"));
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT")
      throw new LockError(`no lockfile at ${lockPath}; run \`failfirst baseline\` before the work`, "FF_E_NO_LOCK");
    throw new LockError(`cannot read lockfile ${lockPath}: ${(e as Error).message}`);
  }
  if (!lock || lock.failfirst_lock !== SPEC_VERSION || typeof lock.criteria !== "object" || !lock.criteria)
    throw new LockError(`${lockPath} is not a failfirst v${SPEC_VERSION} lockfile`);
  return lock;
}

export async function verify(criteria: Criterion[], lockPath: string, opts: Options = {}): Promise<[Report, number]> {
  const lock = readLock(lockPath);
  const locked = lock.criteria;
  const obs = opts.observe ?? ((c) => defaultObserve(c, opts.baseDir ?? "."));
  const rows: Array<Record<string, unknown> & { id: string; verdict: string }> = [];
  const ids = new Set<string>();
  for (const c of criteria) {
    ids.add(c.id);
    const base = locked[c.id];
    const row: Record<string, unknown> & { id: string; verdict: string } = { id: c.id, statement: c.statement, judgment: c.judgment, verdict: "" };
    const set = (verdict: string, reason: string) => Object.assign(row, { verdict, reason });
    if (c.judgment) set("awaiting_review", "judgment criteria are never auto-passed");
    else if (!base) set("unbaselined", "not present at baseline; it never had a chance to fail");
    else if (base.hash !== criterionHash(c)) {
      set("modified", "criterion changed since baseline; goalposts moved");
      row.baseline = base.baseline;
    } else if (base.judgment) set("modified", "was a judgment criterion at baseline");
    else {
      row.baseline = base.baseline;
      const b = base.baseline.status;
      if (b === "passed") set("vacuous", "already passed at baseline; carries no information");
      else if (b === "error") set("baseline_error", "baseline run errored; failure was never demonstrated");
      else {
        const now = evaluate(c, await obs(c));
        row.now = now;
        if (now.status === "passed") set("proven", "failed at baseline, passes now, unchanged");
        else if (now.status === "failed") set("still_failing", now.detail);
        else set("error", now.detail);
      }
    }
    rows.push(row);
  }
  for (const [id, base] of Object.entries(locked))
    if (!ids.has(id))
      rows.push({ id, statement: "", judgment: base.judgment, baseline: base.baseline, verdict: "removed", reason: "present at baseline but missing now" });
  const counts: Record<string, number> = {};
  for (const r of rows) counts[r.verdict] = (counts[r.verdict] ?? 0) + 1;
  const auto = rows.filter((r) => r.verdict !== "awaiting_review");
  let status: string, code: number;
  if (!auto.length || auto.some((r) => r.verdict !== "proven")) [status, code] = ["fail", EXIT_FAIL];
  else if (counts.awaiting_review) [status, code] = ["awaiting_review", EXIT_REVIEW];
  else [status, code] = ["pass", EXIT_OK];
  return [{ tool: "failfirst", version: VERSION, phase: "verify", status, exit_code: code, summary: counts, criteria: rows }, code];
}

export function formatReport(report: Report): string {
  const lines: string[] = [];
  if (report.phase === "baseline") {
    lines.push("failfirst baseline");
    for (const r of report.criteria as Array<Record<string, any>>) {
      const tag = r.judgment ? "JUDGMENT " : ({ failed: "FAILS ok ", passed: "VACUOUS  ", error: "ERROR    " } as Record<string, string>)[r.baseline.status];
      lines.push(`  ${tag} ${r.id}: ${r.statement || r.baseline.detail}`);
    }
    const s = report.summary;
    lines.push(`${s.failed_as_required} failed as required, ${s.vacuous} vacuous, ${s.errored} errored, ${s.judgment} awaiting judgment`);
    if (report.exit_code) lines.push("WARNING: some criteria did not fail at baseline; they will not count.");
  } else {
    lines.push("failfirst verify");
    for (const r of report.criteria as Array<Record<string, any>>) lines.push(`  ${String(r.verdict).toUpperCase().padEnd(16)} ${r.id}: ${r.reason}`);
    lines.push(Object.entries(report.summary).sort().map(([k, n]) => `${n} ${k}`).join(", "));
    lines.push(({
      pass: "PASS: every criterion was proven (failed first, passes now).",
      fail: "FAIL: not every criterion is proven.",
      awaiting_review: "AWAITING REVIEW: all machine checks proven; judgment criteria need a human.",
    } as Record<string, string>)[report.status]);
  }
  return lines.join("\n");
}
