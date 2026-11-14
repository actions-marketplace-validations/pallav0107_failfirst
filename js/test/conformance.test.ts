import { mkdtempSync, readdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { baseline, criterionHash, evaluate, normalizeCriteria, verify } from "../src/index.js";

const ROOT = join(__dirname, "..", "..", "conformance");
const files = readdirSync(ROOT).filter((f) => f.endsWith(".json")).sort();

describe("conformance vectors", () => {
  it("are present", () => expect(files.length).toBeGreaterThan(0));
  for (const f of files) {
    const vectors = JSON.parse(readFileSync(join(ROOT, f), "utf8")).vectors as any[];
    for (const vec of vectors) {
      it(`${f}::${vec.name}`, async () => {
        if (vec.hash) {
          expect(criterionHash(normalizeCriteria([vec.criterion])[0])).toBe(vec.hash);
          return;
        }
        const crit = normalizeCriteria(vec.criteria);
        if (vec.evaluate) {
          for (const c of vec.evaluate) {
            expect(evaluate(crit.find((x) => x.id === c.id)!, c.observation).status).toBe(c.status);
          }
          return;
        }
        const lock = join(mkdtempSync(join(tmpdir(), "ff-")), "lock.json");
        const [, bcode] = await baseline(crit, lock, { observe: (c) => vec.baseline_observations[c.id] });
        expect(bcode).toBe(vec.expected.baseline_exit_code);
        const vcrit = normalizeCriteria(vec.verify_criteria ?? vec.criteria);
        const [rep, code] = await verify(vcrit, lock, { observe: (c) => vec.verify_observations[c.id] });
        const verdicts = Object.fromEntries(rep.criteria.map((r) => [r.id, r.verdict]));
        expect(verdicts).toEqual(vec.expected.verdicts);
        expect(rep.status).toBe(vec.expected.status);
        expect(code).toBe(vec.expected.exit_code);
      });
    }
  }
});
