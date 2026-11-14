// Agent-readiness tests (AGENT_UX_SPEC.md items 1-6, 8); mirrors python/tests/test_agent.py.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import Ajv from "ajv";
import Ajv2020 from "ajv/dist/2020.js";
import { describe, expect, it } from "vitest";

const JS = join(__dirname, "..");
const REPO = join(JS, "..");
const CLI = join(JS, "dist", "cli.js");
const CONF = join(REPO, "conformance", "agent");
const ENV = { ...process.env, NO_COLOR: "1" };
const load = (p: string) => JSON.parse(readFileSync(p, "utf8"));
const schema = (name: string) => load(join(JS, "agent", "schemas", `${name}.schema.json`));
const MCP = load(join(CONF, "mcp-schema-2025-06-18.json"));

const ajv2020 = new Ajv2020({ strict: false });
const ajv7 = new Ajv({ strict: false });
ajv7.addSchema(MCP, "mcp");
const mcpCheck = (def: string, doc: unknown) => {
  const v = ajv7.getSchema(`mcp#/definitions/${def}`)!;
  expect(v(doc), JSON.stringify(v.errors)).toBe(true);
};
const validators: Record<string, any> = {};
function validateOutput(doc: any): string {
  const name = doc.error ? "error" : doc.anthropic ? "describe" : doc.phase ? `${doc.phase}-report` : "version";
  const v = validators[name] ?? (validators[name] = ajv2020.compile(schema(name)));
  expect(v(doc), JSON.stringify(v.errors)).toBe(true);
  return name;
}

function run(args: string[], cwd: string, stdio: any = ["ignore", "pipe", "pipe"]) {
  return spawnSync("node", [CLI, ...args], { cwd, env: ENV, encoding: "utf8", stdio, timeout: 30000 });
}
const tmp = () => mkdtempSync(join(tmpdir(), "ffagent-"));

/** tiktoken is not available in Node: word-based approximation, deliberately conservative. */
const approxTokens = (t: string) => Math.floor(Math.max(t.split(/\s+/).filter(Boolean).length * 1.5, t.length / 3.5));

describe("agent docs", () => {
  it("AGENTS.md <= 1500 tokens (approx: max(1.5 x words, chars / 3.5))", () => {
    expect(approxTokens(readFileSync(join(JS, "agent", "AGENTS.md"), "utf8"))).toBeLessThanOrEqual(1500);
  });
  it("llms.txt format and budget", () => {
    const t = readFileSync(join(JS, "agent", "llms.txt"), "utf8");
    expect(t.startsWith("# failfirst\n") && t.includes("\n> ") && t.includes("](")).toBe(true);
    expect(approxTokens(t)).toBeLessThanOrEqual(600);
  });
  it("help within budget", () => {
    expect(approxTokens(run(["--help"], tmp()).stdout)).toBeLessThanOrEqual(700);
  });
  it("packaged copies equal the canonical files", () => {
    const pairs: Array<[string, string]> = [
      ["spec/tools.json", "tools.json"], ["llms.txt", "llms.txt"], ["AGENTS.md", "AGENTS.md"],
      ...["baseline-report", "verify-report", "error", "version", "describe"].map((n): [string, string] => [`schemas/${n}.schema.json`, `schemas/${n}.schema.json`]),
    ];
    for (const [src, dst] of pairs) expect(readFileSync(join(JS, "agent", dst))).toEqual(readFileSync(join(REPO, src)));
  });
});

describe("tool definitions", () => {
  it("describe --json equals the conformance vector", () => {
    const r = run(["describe", "--json"], tmp());
    expect(r.status).toBe(0);
    expect(JSON.parse(r.stdout)).toEqual(load(join(CONF, "describe.json")).expected);
  });
  it("Anthropic, OpenAI and MCP formats validate", () => {
    const doc = JSON.parse(run(["describe", "--json"], tmp()).stdout);
    expect(validateOutput(doc)).toBe("describe");
    for (const t of doc.anthropic) {
      expect(Object.keys(t).sort()).toEqual(["description", "input_schema", "name"]);
      expect(ajv2020.validateSchema(t.input_schema)).toBe(true);
      expect(t.input_schema.type).toBe("object");
    }
    for (const t of doc.openai) {
      expect(t.type).toBe("function");
      expect(Object.keys(t.function).sort()).toEqual(["description", "name", "parameters"]);
      expect(ajv2020.validateSchema(t.function.parameters)).toBe(true);
    }
    mcpCheck("ListToolsResult", { tools: doc.mcp });
    expect(doc.anthropic.map((t: any) => t.name)).toEqual(doc.mcp.map((t: any) => t.name));
  });
});

type Step = string[] | { write: Record<string, string> };
const vectors = load(join(CONF, "errors.json")).vectors as Array<{ name: string; files: Record<string, string>; steps: Step[]; expected: any }>;
const subset = (a: any, e: any): boolean =>
  e && typeof e === "object" ? a && typeof a === "object" && Object.entries(e).every(([k, v]) => k in a && subset(a[k], v)) : a === e;

describe("cli vectors", () => {
  for (const vec of vectors) {
    it(vec.name, () => {
      const d = tmp();
      for (const [n, t] of Object.entries(vec.files)) {
        mkdirSync(dirname(join(d, n)), { recursive: true });
        writeFileSync(join(d, n), t);
      }
      let r: any;
      for (const step of vec.steps) {
        if (Array.isArray(step)) r = run(step, d);
        else for (const [n, t] of Object.entries(step.write)) writeFileSync(join(d, n), t);
      }
      const exp = vec.expected;
      expect(r.status, r.stdout + r.stderr).toBe(exp.exit);
      expect(r.stdout + r.stderr).not.toContain("\x1b");
      if (exp.error_code) {
        const doc = JSON.parse(r.stdout);
        expect(doc.error.code).toBe(exp.error_code);
        expect(doc.error.message && doc.error.hint).toBeTruthy();
        expect(r.stderr).toContain(exp.error_code);
      }
      if (exp.json_contains) expect(subset(JSON.parse(r.stdout), exp.json_contains)).toBe(true);
      if ("lock_exists" in exp) expect(existsSync(join(d, ".failfirst.lock.json"))).toBe(exp.lock_exists);
      if (exp.stdout_lines) expect(r.stdout.trim().split("\n").length).toBe(exp.stdout_lines);
      validateOutput(JSON.parse(r.stdout));
    });
  }
  it("every json output kind is schema valid", () => {
    const d = tmp();
    writeFileSync(join(d, "failfirst.json"), JSON.stringify({ criteria: [{ id: "A", check: { cmd: "test -f flag" } }, { id: "J", judgment: true }, { id: "P", check: { cmd: "true" } }] }));
    const kinds = new Set<string>();
    for (const a of [["baseline", "--json"], ["verify", "--json"], ["describe", "--json"], ["--version", "--json"], ["baseline", "--json"]])
      kinds.add(validateOutput(JSON.parse(run(a, d).stdout)));
    writeFileSync(join(d, "flag"), "x");
    kinds.add(validateOutput(JSON.parse(run(["verify", "--json"], d).stdout)));
    expect([...kinds].sort()).toEqual(["baseline-report", "describe", "error", "verify-report", "version"]);
  });
});

describe("stdin closed", () => {
  const commands = [["baseline", "--json"], ["verify", "--json"], ["describe", "--json"], ["describe"], ["--version"],
    ["baseline", "--dry-run", "--quiet"], ["verify", "--quiet"], ["--help"], ["mcp"], []];
  for (const args of commands) {
    for (const mode of ["ignore", "closed"]) {
      it(`${args.join(" ") || "no-args"} (${mode})`, () => {
        const d = tmp();
        writeFileSync(join(d, "failfirst.json"), JSON.stringify({ criteria: [{ id: "A", check: { cmd: "false" } }] }));
        // "closed": run through sh with fd 0 closed
        const r = mode === "ignore" ? run(args, d) : spawnSync("sh", ["-c", `exec node "$0" "$@" <&-`, CLI, ...args], { cwd: d, env: ENV, encoding: "utf8", timeout: 30000 });
        expect([0, 1, 2, 3]).toContain(r.status);
        expect(r.stdout + r.stderr).not.toContain("\x1b");
      });
    }
  }
});

describe("mcp", () => {
  it("initialize -> tools/list -> tools/call", async () => {
    const d = tmp();
    writeFileSync(join(d, "failfirst.json"), JSON.stringify({ criteria: [{ id: "A", check: { cmd: "test -f flag" } }] }));
    const p = spawn("node", [CLI, "mcp"], { cwd: d, env: ENV, stdio: ["pipe", "pipe", "pipe"] });
    const lines: string[] = [];
    const waiters: Array<(s: string) => void> = [];
    let buf = "";
    p.stdout.on("data", (c) => {
      buf += c;
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const l = buf.slice(0, i);
        buf = buf.slice(i + 1);
        const w = waiters.shift();
        if (w) w(l);
        else lines.push(l);
      }
    });
    let n = 0;
    const send = (method: string, params?: unknown): Promise<any> => {
      n += 1;
      const reply = new Promise<string>((res) => (lines.length ? res(lines.shift()!) : waiters.push(res)));
      p.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: n, method, ...(params ? { params } : {}) }) + "\n");
      return reply.then((l) => JSON.parse(l));
    };
    try {
      const init = await send("initialize", { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "vitest", version: "1" } });
      mcpCheck("InitializeResult", init.result);
      expect(init.result.serverInfo.name).toBe("failfirst");
      p.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");
      const list = (await send("tools/list")).result;
      mcpCheck("ListToolsResult", list);
      expect(list.tools.map((t: any) => t.name)).toEqual(["failfirst_baseline", "failfirst_verify"]);
      let res = (await send("tools/call", { name: "failfirst_baseline", arguments: {} })).result;
      mcpCheck("CallToolResult", res);
      expect(res.isError).toBe(false);
      expect(validateOutput(res.structuredContent)).toBe("baseline-report");
      expect(JSON.parse(res.content[0].text)).toEqual(res.structuredContent);
      writeFileSync(join(d, "flag"), "x");
      res = (await send("tools/call", { name: "failfirst_verify", arguments: {} })).result;
      expect(res.structuredContent.status).toBe("pass");
      res = (await send("tools/call", { name: "failfirst_baseline", arguments: {} })).result;
      expect(res.isError).toBe(true);
      expect(res.structuredContent.error.code).toBe("FF_E_LOCK_EXISTS");
      res = (await send("tools/call", { name: "failfirst_verify", arguments: { bogus: 1 } })).result;
      expect(res.structuredContent.error.code).toBe("FF_E_USAGE");
      expect((await send("tools/call", { name: "nope", arguments: {} })).error.code).toBe(-32602);
      expect((await send("no/such/method")).error.code).toBe(-32601);
    } finally {
      p.stdin.end();
      await new Promise((r) => p.on("close", r));
    }
  });
});

describe("timeout kills the process tree", () => {
  it("grandchildren do not survive", async () => {
    const d = tmp();
    writeFileSync(join(d, "failfirst.json"), JSON.stringify({ criteria: [{ id: "A", check: { cmd: "sleep 60 & echo $! > pid; wait", timeout: 1 } }] }));
    const t0 = Date.now();
    const r = run(["baseline", "--json"], d);
    expect(Date.now() - t0).toBeLessThan(15000);
    expect(JSON.parse(r.stdout).criteria[0].baseline.status).toBe("error");
    const pid = Number(readFileSync(join(d, "pid"), "utf8").trim());
    const alive = () => {
      try {
        process.kill(pid, 0);
        return true;
      } catch {
        return false;
      }
    };
    for (let i = 0; i < 50 && alive(); i++) await new Promise((res) => setTimeout(res, 100));
    const survived = alive();
    if (survived) process.kill(pid, "SIGKILL");
    expect(survived).toBe(false);
  });
});
