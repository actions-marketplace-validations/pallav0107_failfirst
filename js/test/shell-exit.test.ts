import { describe, expect, it } from "vitest";
import { evaluate, normalizeCriteria } from "../src/index.js";

const ev = (check: Record<string, unknown>, exit: number) => {
  const c = normalizeCriteria([{ id: "A", statement: "s", check: { type: "command", ...check } }])[0];
  return evaluate(c, { exit, output: "" });
};

describe("shell exit 127/126 is an error, not a failure", () => {
  it("shell 127 is error", () => {
    const r = ev({ cmd: "nope" }, 127);
    expect(r.status).toBe("error");
    expect(r.detail).toContain("could not find");
    expect(r.detail).toContain("127");
  });
  it("shell 126 is error", () => {
    const r = ev({ cmd: "nope" }, 126);
    expect(r.status).toBe("error");
    expect(r.detail).toContain("could not execute");
    expect(r.detail).toContain("126");
  });
  it("shell 127 with expect_exit 127 passes", () => {
    expect(ev({ cmd: "x", expect_exit: 127 }, 127).status).toBe("passed");
  });
  it("shell 126 with expect_exit 127 is error", () => {
    expect(ev({ cmd: "x", expect_exit: 127 }, 126).status).toBe("error");
  });
  it("argv 127 is failed", () => {
    expect(ev({ argv: ["x"] }, 127).status).toBe("failed");
  });
  it("other exit unchanged", () => {
    expect(ev({ cmd: "x" }, 1).status).toBe("failed");
  });
});
