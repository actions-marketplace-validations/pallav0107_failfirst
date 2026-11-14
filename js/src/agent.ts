// Agent-facing layer: tool definitions (one source of truth), stable errors, shared operations.
// agent/tools.json is copied from the repo's spec/tools.json by tools/sync_agent.py; the Anthropic,
// OpenAI and MCP formats printed by `failfirst describe --json` are all derived from it.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { baseline, DEFAULT_LOCK, LockError, verify, VERSION, type Report } from "./core.js";
import { loadCriteria, SpecError } from "./model.js";

/** JSON Schema (draft 2020-12 subset) describing a tool's arguments. */
export interface InputSchema {
  type: "object";
  properties: Record<string, { type: string; description?: string }>;
  additionalProperties?: boolean;
}
/** One tool as written in tools.json. */
export interface ToolSpec {
  name: string;
  description: string;
  input_schema: InputSchema;
  output_schema: string;
}
/** Parsed tools.json. */
export interface ToolsFile {
  tool: string;
  tools: ToolSpec[];
  errors: Record<string, { exit: number; hint: string }>;
}
/** Output of `failfirst describe --json`. */
export interface Description {
  tool: "failfirst";
  version: string;
  anthropic: Array<{ name: string; description: string; input_schema: InputSchema }>;
  openai: Array<{ type: "function"; function: { name: string; description: string; parameters: InputSchema } }>;
  mcp: Array<{ name: string; description: string; inputSchema: InputSchema }>;
}

const AGENT_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "agent");
const CANDIDATES = ["failfirst.yaml", "failfirst.yml", "failfirst.json", "criteria.yaml", "criteria.yml", "criteria.json"];

let cached: ToolsFile | undefined;
/** Return the parsed tools.json (tools plus the stable error table). */
export function loadTools(): ToolsFile {
  cached ??= JSON.parse(readFileSync(join(AGENT_DIR, "tools.json"), "utf8")) as ToolsFile;
  return cached;
}

/** An expected failure with a stable `code` (FF_E_*), a message and a static hint. */
export class CliError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
  /** Process exit status for this error code. */
  get exitCode(): number {
    return loadTools().errors[this.code]?.exit ?? 70;
  }
  /** The `{"error": {code, message, hint}}` document printed with `--json`. */
  payload(): { error: { code: string; message: string; hint: string } } {
    return { error: { code: this.code, message: this.message, hint: loadTools().errors[this.code]?.hint ?? "" } };
  }
}

/** Tool definitions in Anthropic, OpenAI and MCP formats, all derived from tools.json. */
export function describe(): Description {
  const tools = loadTools().tools;
  return {
    tool: "failfirst",
    version: VERSION,
    anthropic: tools.map((t) => ({ name: t.name, description: t.description, input_schema: t.input_schema })),
    openai: tools.map((t) => ({ type: "function" as const, function: { name: t.name, description: t.description, parameters: t.input_schema } })),
    mcp: tools.map((t) => ({ name: t.name, description: t.description, inputSchema: t.input_schema })),
  };
}

function checkArgs(schema: InputSchema, args: unknown): asserts args is Record<string, unknown> {
  if (args === null || typeof args !== "object" || Array.isArray(args)) throw new CliError("FF_E_USAGE", "tool arguments must be an object");
  for (const [key, value] of Object.entries(args)) {
    const prop = schema.properties[key];
    if (!prop) throw new CliError("FF_E_USAGE", `unknown argument '${key}'`);
    if (typeof value !== prop.type) throw new CliError("FF_E_USAGE", `argument '${key}' must be a ${prop.type}`);
  }
}

/** Resolve the criteria path, searching the default names in the working directory. */
export function findCriteria(criteria?: string): string {
  if (criteria) {
    if (!existsSync(criteria)) throw new CliError("FF_E_NO_CRITERIA", `criteria file not found: ${criteria}`);
    return criteria;
  }
  const found = CANDIDATES.find((n) => existsSync(n));
  if (!found) throw new CliError("FF_E_NO_CRITERIA", `no criteria file found (tried ${CANDIDATES.join(", ")})`);
  return found;
}

/** Run failfirst_baseline or failfirst_verify; resolves to [report, exitCode] or throws CliError. */
export async function runOperation(name: string, args: Record<string, unknown>): Promise<[Report, number]> {
  const spec = loadTools().tools.find((t) => t.name === name);
  if (!spec) throw new CliError("FF_E_USAGE", `unknown tool '${name}'`);
  checkArgs(spec.input_schema, args);
  const path = findCriteria(args.criteria as string | undefined);
  let criteria;
  try {
    criteria = loadCriteria(path);
  } catch (e) {
    if (e instanceof SpecError) throw new CliError("FF_E_BAD_CRITERIA", e.message);
    throw new CliError("FF_E_BAD_CRITERIA", `cannot read ${path}: ${(e as Error).message}`);
  }
  const baseDir = dirname(resolve(path));
  const lock = (args.lock as string | undefined) || join(baseDir, DEFAULT_LOCK);
  try {
    return name === "failfirst_baseline"
      ? await baseline(criteria, lock, { baseDir, force: !!args.force, dryRun: !!args.dry_run })
      : await verify(criteria, lock, { baseDir });
  } catch (e) {
    if (e instanceof LockError) throw new CliError(e.code, e.message);
    if ((e as NodeJS.ErrnoException).code?.startsWith("E")) throw new CliError("FF_E_IO", `cannot write ${lock}: ${(e as Error).message}`);
    throw e;
  }
}
