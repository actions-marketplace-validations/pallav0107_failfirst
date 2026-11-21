// Observation (running a check) and evaluation (judging an observation).
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Check, Criterion } from "./model.js";

export interface Observation {
  exit?: number;
  output?: string;
  content?: string;
  missing?: boolean;
  status?: number;
  body?: string;
  error?: string;
}
export interface Evaluation {
  status: "passed" | "failed" | "error";
  detail: string;
}

export async function observe(criterion: Criterion, baseDir = "."): Promise<Observation> {
  const check = criterion.check as Check;
  if (check.type === "command") return observeCommand(check, baseDir);
  if (check.type === "file_contains") {
    try {
      return { content: readFileSync(join(baseDir, check.path as string)).toString("utf8") };
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === "ENOENT") return { missing: true };
      return { error: `cannot read file: ${(e as Error).message}` };
    }
  }
  return observeHttp(check);
}

/** Kill a process and everything it spawned (its whole process group; taskkill /T on Windows). */
function killTree(pid: number | undefined): void {
  if (pid === undefined) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore" });
    return;
  }
  try {
    process.kill(-pid, "SIGKILL");
  } catch {
    try {
      process.kill(pid, "SIGKILL");
    } catch {
      /* already gone */
    }
  }
}

function observeCommand(check: Check, baseDir: string): Promise<Observation> {
  const cwd = join(baseDir, check.cwd ?? ".");
  const timeoutS = check.timeout ?? 60;
  return new Promise((resolve) => {
    const opts = { cwd, stdio: ["ignore", "pipe", "pipe"] as ["ignore", "pipe", "pipe"], detached: process.platform !== "win32" };
    let child: ChildProcess;
    try {
      child = check.argv ? spawn(check.argv[0], check.argv.slice(1), opts) : spawn(check.cmd as string, { ...opts, shell: true });
    } catch (e) {
      resolve({ error: `cannot start: ${(e as Error).message}` });
      return;
    }
    const out: Buffer[] = [];
    const err: Buffer[] = [];
    let done = false;
    const finish = (obs: Observation) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve(obs);
    };
    const timer = setTimeout(() => {
      killTree(child.pid);
      child.stdout?.destroy();
      child.stderr?.destroy();
      finish({ error: `timeout after ${timeoutS}s` });
    }, timeoutS * 1000);
    child.stdout?.on("data", (c: Buffer) => out.push(c));
    child.stderr?.on("data", (c: Buffer) => err.push(c));
    child.on("error", (e) => finish({ error: `cannot start: ${e.message}` }));
    child.on("close", (code, signal) => {
      if (code === null) finish({ error: `killed by signal ${signal}` });
      else finish({ exit: code, output: Buffer.concat(out).toString("utf8") + Buffer.concat(err).toString("utf8") });
    });
  });
}

async function observeHttp(check: Check): Promise<Observation> {
  try {
    const res = await fetch(check.url as string, {
      method: check.method,
      signal: AbortSignal.timeout((check.timeout ?? 30) * 1000),
    });
    return { status: res.status, body: await res.text() };
  } catch (e) {
    return { error: `request failed: ${(e as Error).message}` };
  }
}

function textChecks(check: Check, text: string): string | null {
  for (const s of check.expect_contains) if (!text.includes(s)) return `output missing expected text ${JSON.stringify(s)}`;
  for (const s of check.expect_not_contains) if (text.includes(s)) return `output contains forbidden text ${JSON.stringify(s)}`;
  return null;
}

// POSIX shell statuses that mean the command never ran (spec section 2).
const SHELL_EXIT: Record<number, string> = {
  127: "shell could not find the command",
  126: "shell could not execute the command",
};

export function evaluate(criterion: Criterion, obs: Observation): Evaluation {
  const check = criterion.check as Check;
  if (obs.error !== undefined) return { status: "error", detail: String(obs.error) };
  let problem: string | null;
  if (check.type === "command") {
    const shellMsg = check.cmd !== undefined && obs.exit !== check.expect_exit ? SHELL_EXIT[obs.exit as number] : undefined;
    if (shellMsg) return { status: "error", detail: `${shellMsg} (exit ${obs.exit})` };
    if (obs.exit !== check.expect_exit) return { status: "failed", detail: `exit ${obs.exit}, expected ${check.expect_exit}` };
    problem = textChecks(check, obs.output ?? "");
  } else if (check.type === "file_contains") {
    if (obs.missing) return { status: "failed", detail: "file does not exist" };
    problem = textChecks(check, obs.content ?? "");
  } else {
    if (obs.status !== check.expect_status) return { status: "failed", detail: `status ${obs.status}, expected ${check.expect_status}` };
    problem = textChecks(check, obs.body ?? "");
  }
  return problem ? { status: "failed", detail: problem } : { status: "passed", detail: "ok" };
}
