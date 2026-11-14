#!/usr/bin/env node
// Command line: failfirst baseline | verify | describe | mcp.
// Agent-safe: never prompts, never reads stdin (except `mcp`, which speaks the protocol on it),
// never emits ANSI colour. Expected failures print {"error": {code, message, hint}} on stdout with
// --json (text on stderr otherwise) and exit 2.
import { writeFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { CliError, describe, loadTools, runOperation } from "./agent.js";
import { DEFAULT_LOCK, formatReport, VERSION, type Report } from "./core.js";
import { serve } from "./mcp.js";

const USAGE = `usage: failfirst <command> [options]
commands:
  baseline [criteria] [--lock P] [--dry-run] [--force] [--report P]   run on the unfixed state, write ${DEFAULT_LOCK}
  verify   [criteria] [--lock P] [--report P]                        re-run; a criterion counts only if proven
  describe                                                           tool definitions (Anthropic, OpenAI, MCP)
  mcp                                                                MCP server on stdio
common options: --json (JSON output)  --quiet (one line / compact JSON)  --version  --help
exit: 0 pass, 1 fail, 2 usage/input error, 3 awaiting human review, 70 internal`;

const dump = (obj: unknown, compact: boolean) => JSON.stringify(obj, null, compact ? undefined : 2);

function quietLine(r: Report): string {
  const summ = Object.entries(r.summary).sort(([a], [b]) => (a < b ? -1 : 1)).map(([k, n]) => `${n} ${k}`).join(", ");
  return `failfirst ${r.phase}: ${r.status} (${summ})`;
}

const OPTIONS = {
  json: { type: "boolean" },
  quiet: { type: "boolean" },
  lock: { type: "string" },
  report: { type: "string" },
  force: { type: "boolean" },
  "dry-run": { type: "boolean" },
} as const;
const ALLOWED: Record<string, string[]> = {
  baseline: ["json", "quiet", "lock", "report", "force", "dry-run"],
  verify: ["json", "quiet", "lock", "report"],
  describe: ["json", "quiet"],
  mcp: ["json"],
};

async function run(argv: string[]): Promise<number> {
  if (argv.includes("--help") || argv.includes("-h")) {
    console.log(USAGE);
    return 0;
  }
  if (argv.length === 1 && argv[0] === "--version") {
    console.log(`failfirst ${VERSION}`);
    return 0;
  }
  if (argv.length === 2 && argv.includes("--version") && argv.includes("--json")) {
    console.log(dump({ tool: "failfirst", version: VERSION }, false));
    return 0;
  }
  const [cmd, ...rest] = argv;
  if (cmd === undefined || cmd.startsWith("-")) throw new CliError("FF_E_USAGE", "a command is required (baseline, verify, describe, mcp)");
  if (!(cmd in ALLOWED)) throw new CliError("FF_E_USAGE", `unknown command '${cmd}'`);
  const options = Object.fromEntries(ALLOWED[cmd].map((k) => [k, OPTIONS[k as keyof typeof OPTIONS]]));
  const { values, positionals } = parseArgs({ args: rest, allowPositionals: true, options });
  const maxPos = cmd === "baseline" || cmd === "verify" ? 1 : 0;
  if (positionals.length > maxPos) throw new CliError("FF_E_USAGE", `unexpected argument '${positionals[maxPos]}'`);
  const asJson = !!values.json;
  const quiet = !!values.quiet;
  if (cmd === "describe") {
    if (asJson) console.log(dump(describe(), quiet));
    else for (const t of loadTools().tools) console.log(`${t.name}: ${t.description.split(". ")[0].replace(/\.$/, "")}.`);
    return 0;
  }
  if (cmd === "mcp") return serve();
  const toolArgs: Record<string, unknown> = {};
  if (positionals[0]) toolArgs.criteria = positionals[0];
  if (values.lock) toolArgs.lock = values.lock;
  if (cmd === "baseline") Object.assign(toolArgs, { force: !!values.force, dry_run: !!values["dry-run"] });
  const [report, code] = await runOperation(`failfirst_${cmd}`, toolArgs);
  if (values.report && !(cmd === "baseline" && values["dry-run"])) {
    try {
      writeFileSync(values.report as string, JSON.stringify(report, null, 2));
    } catch (e) {
      throw new CliError("FF_E_IO", `cannot write ${values.report}: ${(e as Error).message}`);
    }
  }
  console.log(asJson ? dump(report, quiet) : quiet ? quietLine(report) : formatReport(report));
  return code;
}

export async function main(argv: string[]): Promise<number> {
  const asJson = argv.includes("--json");
  let err: CliError;
  try {
    return await run(argv);
  } catch (e) {
    const code = (e as NodeJS.ErrnoException).code;
    if (e instanceof CliError) err = e;
    else if (typeof code === "string" && code.startsWith("ERR_PARSE_ARGS")) err = new CliError("FF_E_USAGE", (e as Error).message);
    else err = new CliError("FF_E_INTERNAL", `${(e as Error).name}: ${(e as Error).message}`);
  }
  const info = err.payload().error;
  console.error(`failfirst: ${info.code}: ${info.message}\n  hint: ${info.hint}`);
  if (asJson) console.log(dump(err.payload(), false));
  return err.exitCode;
}

main(process.argv.slice(2)).then((c) => process.exit(c));
