// Minimal MCP server over stdio (newline-delimited JSON-RPC 2.0): `failfirst mcp`.
// Implements initialize, ping, tools/list and tools/call; other requests get error -32601.
import { createInterface } from "node:readline";
import { CliError, describe, runOperation } from "./agent.js";
import { VERSION } from "./core.js";

const SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"];

type Json = Record<string, unknown>;

const result = (id: unknown, r: Json): Json => ({ jsonrpc: "2.0", id, result: r });
const error = (id: unknown, code: number, message: string): Json => ({ jsonrpc: "2.0", id, error: { code, message } });

async function call(params: Json): Promise<Json> {
  try {
    const [report] = await runOperation(String(params.name), (params.arguments ?? {}) as Json);
    return { content: [{ type: "text", text: JSON.stringify(report, null, 2) }], structuredContent: report, isError: false };
  } catch (e) {
    if (!(e instanceof CliError)) throw e;
    const payload = e.payload();
    return { content: [{ type: "text", text: JSON.stringify(payload, null, 2) }], structuredContent: payload, isError: true };
  }
}

/** Handle one decoded JSON-RPC message; resolves to the response, or null for notifications. */
export async function handle(msg: unknown): Promise<Json | null> {
  if (msg === null || typeof msg !== "object" || Array.isArray(msg) || !("method" in msg)) {
    const id = msg && typeof msg === "object" && "id" in msg ? (msg as Json).id : null;
    return error(id, -32600, "invalid request");
  }
  const m = msg as Json;
  if (!("id" in m)) return null;
  const params = (m.params ?? {}) as Json;
  switch (m.method) {
    case "initialize": {
      const asked = params.protocolVersion as string;
      return result(m.id, {
        protocolVersion: SUPPORTED.includes(asked) ? asked : SUPPORTED[0],
        capabilities: { tools: {} },
        serverInfo: { name: "failfirst", version: VERSION },
      });
    }
    case "ping":
      return result(m.id, {});
    case "tools/list":
      return result(m.id, { tools: describe().mcp });
    case "tools/call":
      if (!describe().mcp.some((t) => t.name === params.name)) return error(m.id, -32602, `unknown tool '${String(params.name)}'`);
      return result(m.id, await call(params));
    default:
      return error(m.id, -32601, `method not found: ${String(m.method)}`);
  }
}

/** Serve until stdin closes. */
export async function serve(): Promise<number> {
  const rl = createInterface({ input: process.stdin });
  let chain: Promise<void> = Promise.resolve();
  rl.on("line", (line) => {
    if (!line.trim()) return;
    chain = chain.then(async () => {
      let reply: Json | null;
      try {
        reply = await handle(JSON.parse(line));
      } catch (e) {
        reply = e instanceof SyntaxError ? error(null, -32700, "parse error") : error(null, -32603, String(e));
      }
      if (reply) process.stdout.write(JSON.stringify(reply) + "\n");
    });
  });
  await new Promise<void>((done) => rl.on("close", () => done()));
  await chain;
  return 0;
}
