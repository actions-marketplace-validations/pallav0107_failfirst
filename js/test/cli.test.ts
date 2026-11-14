import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { loadCriteria, SpecError } from "../src/index.js";

const CLI = join(__dirname, "..", "dist", "cli.js");
const run = (cwd: string, ...args: string[]) => spawnSync("node", [CLI, ...args], { cwd, encoding: "utf8" });
const NODE = JSON.stringify(process.execPath);

function setup() {
  const d = mkdtempSync(join(tmpdir(), "ffcli-"));
  const spec = {
    criteria: [
      { id: "A", statement: "flag exists", check: { cmd: `${NODE} -e "process.exit(require('fs').existsSync('flag')?0:1)"` } },
      { id: "J", statement: "reads well", judgment: true },
    ],
  };
  writeFileSync(join(d, "failfirst.json"), JSON.stringify(spec));
  return { d, spec };
}

describe("cli", () => {
  it("full flow with real commands", () => {
    const { d } = setup();
    expect(run(d, "baseline").status).toBe(0);
    expect(run(d, "verify").status).toBe(1);
    writeFileSync(join(d, "flag"), "x");
    const r = run(d, "verify", "--json");
    expect(r.status).toBe(3);
    expect(JSON.parse(r.stdout).status).toBe("awaiting_review");
  });
  it("edit after baseline invalidates", () => {
    const { d, spec } = setup();
    run(d, "baseline");
    writeFileSync(join(d, "flag"), "x");
    (spec.criteria[0] as any).check.cmd = "true";
    writeFileSync(join(d, "failfirst.json"), JSON.stringify(spec));
    const r = run(d, "verify");
    expect(r.status).toBe(1);
    expect(r.stdout).toContain("MODIFIED");
  });
  it("vacuous baseline", () => {
    const { d } = setup();
    writeFileSync(join(d, "flag"), "x");
    expect(run(d, "baseline").status).toBe(1);
    expect(run(d, "verify").stdout).toContain("VACUOUS");
  });
  it("refuses overwrite and missing lock", () => {
    const { d } = setup();
    expect(run(d, "verify").status).toBe(2);
    run(d, "baseline");
    expect(run(d, "baseline").status).toBe(2);
    expect(run(d, "baseline", "--force").status).toBe(0);
  });
  it("timeout is an error, not a failure", () => {
    const d = mkdtempSync(join(tmpdir(), "ffcli-"));
    writeFileSync(join(d, "failfirst.json"), JSON.stringify({ criteria: [{ id: "A", check: { argv: ["sleep", "5"], timeout: 1 } }] }));
    expect(run(d, "baseline").status).toBe(1);
    expect(JSON.parse(readFileSync(join(d, ".failfirst.lock.json"), "utf8")).criteria.A.baseline.status).toBe("error");
  });
  it("yaml equals json; invalid specs rejected", () => {
    const d = mkdtempSync(join(tmpdir(), "ffcli-"));
    writeFileSync(join(d, "c.yaml"), "criteria:\n  - id: A\n    check: {cmd: 'true'}\n");
    writeFileSync(join(d, "c.json"), JSON.stringify({ criteria: [{ id: "A", check: { cmd: "true" } }] }));
    expect(loadCriteria(join(d, "c.yaml"))).toEqual(loadCriteria(join(d, "c.json")));
    const bad = [
      { criteria: [] },
      { criteria: [{ id: "A", check: { cmd: "x" } }, { id: "A", check: { cmd: "x" } }] },
      { criteria: [{ id: "A", check: { cmd: "x", expect_exti: 1 } }] },
      { criteria: [{ id: "A", judgment: true, check: { cmd: "x" } }] },
      { criteria: [{ id: "A" }] },
      { criteria: [{ id: "A", check: { cmd: "x", argv: ["x"] } }] },
    ];
    for (const b of bad) {
      writeFileSync(join(d, "b.json"), JSON.stringify(b));
      expect(() => loadCriteria(join(d, "b.json"))).toThrow(SpecError);
    }
  });
});
