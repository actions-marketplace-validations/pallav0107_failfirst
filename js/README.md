# @pallav0107/failfirst (TypeScript / Node)

Acceptance criteria that must be **proven to fail on the unfixed code** before they may count as passing. A check that has never failed carries no information.

```
npm i -g @pallav0107/failfirst
failfirst baseline        # before the work; writes .failfirst.lock.json
failfirst verify          # after; passes only if every criterion failed first, passes now, and is unchanged
```

Library:

```ts
import { loadCriteria, baseline, verify, formatReport } from "@pallav0107/failfirst";

const criteria = loadCriteria("failfirst.yaml");
await baseline(criteria, ".failfirst.lock.json");
// ... do the work ...
const [report, code] = await verify(criteria, ".failfirst.lock.json");
console.log(formatReport(report));
```

Exit codes: 0 pass, 1 fail, 2 bad input, 3 judgment criteria awaiting human review.

Same behaviour as the Python package; both pass the shared conformance vectors (`conformance/`). Spec: `spec/SPEC.md`. MIT licensed.

## Agent use

`failfirst describe --json` (Anthropic / OpenAI / MCP tool definitions), `failfirst mcp` (MCP stdio server), `--json` on every command, stable `FF_E_*` error codes. See `agent/AGENTS.md` and `agent/llms.txt` in this package.
