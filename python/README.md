# failfirst (Python)

Acceptance criteria that must be **proven to fail on the unfixed code** before they may count as passing. A check that has never failed carries no information.

```
pip install failfirst
failfirst baseline        # before the work; writes .failfirst.lock.json
failfirst verify          # after; passes only if every criterion failed first, passes now, and is unchanged
```

Library:

```python
from failfirst import load_criteria, baseline, verify, format_report

criteria = load_criteria("failfirst.yaml")
report, code = baseline(criteria, ".failfirst.lock.json")
# ... do the work ...
report, code = verify(criteria, ".failfirst.lock.json")
print(format_report(report))
```

Exit codes: 0 pass, 1 fail, 2 bad input, 3 judgment criteria awaiting human review.

Full documentation, the language-neutral spec and the conformance vectors: see the repository root (`spec/SPEC.md`). MIT licensed.

## Agent use

`failfirst describe --json` (Anthropic / OpenAI / MCP tool definitions), `failfirst mcp` (MCP stdio server), `--json` on every command, stable `FF_E_*` error codes. See `agent/AGENTS.md` and `agent/llms.txt` in this package.
