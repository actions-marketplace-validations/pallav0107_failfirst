// Criterion model: validation, normalisation and content hashing (see spec/SPEC.md).
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { parse as parseYaml } from "yaml";

export const SPEC_VERSION = 1;

export class SpecError extends Error {}

export interface Check {
  type: "command" | "file_contains" | "http";
  cmd?: string;
  argv?: string[];
  cwd?: string;
  path?: string;
  url?: string;
  method?: string;
  timeout?: number;
  expect_exit?: number;
  expect_status?: number;
  expect_contains: string[];
  expect_not_contains: string[];
}

export interface Criterion {
  id: string;
  statement: string;
  judgment: boolean;
  check: Check | null;
}

const CHECK_FIELDS: Record<string, Set<string>> = {
  command: new Set(["type", "cmd", "argv", "cwd", "timeout", "expect_exit", "expect_contains", "expect_not_contains"]),
  file_contains: new Set(["type", "path", "expect_contains", "expect_not_contains"]),
  http: new Set(["type", "url", "method", "timeout", "expect_status", "expect_contains", "expect_not_contains"]),
};

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isInt = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v);

function strList(cid: string, key: string, v: unknown): string[] {
  if (v === undefined || v === null) return [];
  if (typeof v === "string") return [v];
  if (Array.isArray(v) && v.every((x) => typeof x === "string")) return [...v];
  throw new SpecError(`criterion '${cid}': ${key} must be a string or list of strings`);
}

function intField(cid: string, key: string, v: unknown, dflt: number, min?: number): number {
  if (v === undefined || v === null) return dflt;
  if (!isInt(v)) throw new SpecError(`criterion '${cid}': ${key} must be an integer`);
  if (min !== undefined && v < min) throw new SpecError(`criterion '${cid}': ${key} must be >= ${min}`);
  return v;
}

export function normalizeCriterion(raw: unknown): Criterion {
  if (!isObj(raw)) throw new SpecError("each criterion must be an object");
  const cid = raw.id;
  if (typeof cid !== "string" || !cid) throw new SpecError("each criterion needs a non-empty string id");
  const extra = Object.keys(raw).filter((k) => !["id", "statement", "judgment", "check"].includes(k));
  if (extra.length) throw new SpecError(`criterion '${cid}': unknown field(s) ${JSON.stringify(extra.sort())}`);
  const statement = raw.statement ?? "";
  if (typeof statement !== "string") throw new SpecError(`criterion '${cid}': statement must be a string`);
  const judgment = raw.judgment ?? false;
  if (typeof judgment !== "boolean") throw new SpecError(`criterion '${cid}': judgment must be true or false`);
  const check = raw.check;
  if (judgment) {
    if (check !== undefined && check !== null)
      throw new SpecError(`criterion '${cid}': a judgment criterion must not have a check`);
    return { id: cid, statement, judgment: true, check: null };
  }
  if (!isObj(check)) throw new SpecError(`criterion '${cid}': needs a check object (or judgment: true)`);
  return { id: cid, statement, judgment: false, check: normalizeCheck(cid, check) };
}

function normalizeCheck(cid: string, check: Obj): Check {
  const ctype = (check.type ?? ("cmd" in check || "argv" in check ? "command" : undefined)) as string;
  if (!(ctype in CHECK_FIELDS))
    throw new SpecError(`criterion '${cid}': check.type must be one of ${JSON.stringify(Object.keys(CHECK_FIELDS).sort())}`);
  const extra = Object.keys(check).filter((k) => !CHECK_FIELDS[ctype].has(k));
  if (extra.length) throw new SpecError(`criterion '${cid}': unknown check field(s) ${JSON.stringify(extra.sort())}`);
  const has = strList(cid, "expect_contains", check.expect_contains);
  const hasnt = strList(cid, "expect_not_contains", check.expect_not_contains);
  const out: Obj = { type: ctype };
  if (ctype === "command") {
    const { cmd, argv } = check;
    if ((cmd === undefined || cmd === null) === (argv === undefined || argv === null))
      throw new SpecError(`criterion '${cid}': command check needs exactly one of cmd or argv`);
    if (cmd !== undefined && cmd !== null) {
      if (typeof cmd !== "string" || !cmd.trim()) throw new SpecError(`criterion '${cid}': cmd must be a non-empty string`);
      out.cmd = cmd;
    } else {
      if (!(Array.isArray(argv) && argv.length && argv.every((a) => typeof a === "string")))
        throw new SpecError(`criterion '${cid}': argv must be a non-empty list of strings`);
      out.argv = [...(argv as string[])];
    }
    const cwd = check.cwd ?? ".";
    if (typeof cwd !== "string") throw new SpecError(`criterion '${cid}': cwd must be a string`);
    out.cwd = cwd;
    out.timeout = intField(cid, "timeout", check.timeout, 60, 1);
    out.expect_exit = intField(cid, "expect_exit", check.expect_exit, 0);
  } else if (ctype === "file_contains") {
    if (typeof check.path !== "string" || !check.path) throw new SpecError(`criterion '${cid}': file_contains needs a path`);
    if (!has.length && !hasnt.length)
      throw new SpecError(`criterion '${cid}': file_contains needs expect_contains or expect_not_contains`);
    out.path = check.path;
  } else {
    if (typeof check.url !== "string" || !check.url) throw new SpecError(`criterion '${cid}': http check needs a url`);
    out.url = check.url;
    const method = check.method ?? "GET";
    if (typeof method !== "string") throw new SpecError(`criterion '${cid}': method must be a string`);
    out.method = method.toUpperCase();
    out.timeout = intField(cid, "timeout", check.timeout, 30, 1);
    out.expect_status = intField(cid, "expect_status", check.expect_status, 200);
  }
  out.expect_contains = has;
  out.expect_not_contains = hasnt;
  return out as unknown as Check;
}

export function normalizeCriteria(rawList: unknown): Criterion[] {
  if (!Array.isArray(rawList) || !rawList.length) throw new SpecError("criteria must be a non-empty list");
  const seen = new Set<string>();
  return rawList.map((r) => {
    const c = normalizeCriterion(r);
    if (seen.has(c.id)) throw new SpecError(`duplicate criterion id '${c.id}'`);
    seen.add(c.id);
    return c;
  });
}

function sortKeys(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (isObj(v)) {
    const o: Obj = {};
    for (const k of Object.keys(v).sort()) o[k] = sortKeys(v[k]);
    return o;
  }
  return v;
}

/** Sorted keys, no whitespace, non-ASCII raw. Identical across implementations. */
export function canonicalJson(obj: unknown): string {
  return JSON.stringify(sortKeys(obj));
}

export function criterionHash(normalized: Criterion): string {
  return createHash("sha256").update(canonicalJson(normalized), "utf8").digest("hex");
}

export function loadCriteria(path: string): Criterion[] {
  const text = readFileSync(path, "utf8");
  let doc: unknown;
  try {
    doc = /\.ya?ml$/i.test(path) ? parseYaml(text) : JSON.parse(text);
  } catch (e) {
    throw new SpecError(`cannot parse ${path}: ${(e as Error).message}`);
  }
  if (!isObj(doc) || !("criteria" in doc)) throw new SpecError("criteria file must be an object with a 'criteria' list");
  if ((doc.version ?? SPEC_VERSION) !== SPEC_VERSION) throw new SpecError(`unsupported criteria version ${String(doc.version)}`);
  return normalizeCriteria(doc.criteria);
}
