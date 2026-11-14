# failfirst: agent guide

Rule: a criterion counts only if it FAILED before the work, is UNCHANGED, and PASSES now.

## Commands (always add `--json`; run in the project directory)
- `failfirst baseline [criteria] [--lock P] [--dry-run] [--force] [--quiet] [--json]`
  Run once, BEFORE any work, on the unfixed state. Writes `.failfirst.lock.json` next to the criteria file.
- `failfirst verify [criteria] [--lock P] [--quiet] [--json]` run AFTER the work.
- `failfirst describe --json` tool definitions (Anthropic, OpenAI, MCP). `failfirst mcp` MCP server on stdio
  (tools `failfirst_baseline`, `failfirst_verify`). `failfirst --version`.
- `criteria` defaults to the first existing of failfirst.yaml|yml|json, criteria.yaml|yml|json.
- Never reads stdin, never prompts, never prints ANSI colour.

## Criteria file (failfirst.yaml or .json)
```yaml
criteria:
  - id: add-works                # unique
    statement: add(2, 3) returns 5
    check: { cmd: 'python3 -c "from calc import add; assert add(2,3)==5"' }
  - id: reads-well
    judgment: true               # a human decides; never auto-passed
```
Checks: `cmd` (shell string) or `argv` (list) with `cwd`, `timeout` (s, default 60), `expect_exit` (default 0);
`type: file_contains` with `path`; `type: http` with `url`, `expect_status`. Optional on all:
`expect_contains`, `expect_not_contains`. Unknown fields are an error.

## Exit codes
0 pass / baseline ok; 1 fail (or baseline found criteria that already pass or errored); 2 input error;
3 all machine criteria proven, judgment criteria await a human; 70 internal.

## Output
Reports: `{tool, version, phase, status, exit_code, summary, criteria[]}`. Verify verdict per criterion:
`proven` good; `still_failing` keep working; `modified`/`removed`/`unbaselined` criteria changed after
baseline, so revert the edit; `vacuous` passed at baseline (measures nothing); `baseline_error`;
`error`; `awaiting_review`. Baseline `status`: `ok` or `warning`.
Errors with `--json` (JSON on stdout, text copy on stderr, exit 2): `{"error": {"code", "message", "hint"}}`. Codes: FF_E_USAGE,
FF_E_NO_CRITERIA, FF_E_BAD_CRITERIA, FF_E_LOCK_EXISTS, FF_E_NO_LOCK, FF_E_BAD_LOCK, FF_E_IO (unreadable/unwritable file), FF_E_INTERNAL.

## Examples
1. Before work: `failfirst baseline --json` -> exit 0, every criterion `failed`.
2. Preview only: `failfirst baseline --dry-run --json` (no lockfile written).
3. After work: `failfirst verify --json` -> `"status": "pass"`, exit 0.
4. Pending review: exit 3, `awaiting_review` ids go to a human.
5. MCP: run `failfirst mcp`, send `initialize`, then `tools/call` with name `failfirst_verify`.

## Pitfalls
- Baseline BEFORE the fix. A criterion that already passes is `vacuous`; fix the criterion, not the code.
- Never re-baseline after the fix to make it pass: FF_E_LOCK_EXISTS protects the evidence; `--force`
  is for a human owner only.
- Do not edit a criterion after baseline (`modified`). A timeout or missing command is `error`, not proof.
- Exit 1 on verify is a normal result, not a crash: read `criteria[].verdict`.
- `cwd` and `path` are relative to the criteria file's directory.
