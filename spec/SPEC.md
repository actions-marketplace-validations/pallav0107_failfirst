# failfirst specification, version 1

Language-neutral. Every implementation MUST pass every vector in `conformance/`.

> A check that has never failed carries no information.

## 1. Criteria file

JSON (`.json`) or YAML (`.yaml`/`.yml`). Top level: an object with `criteria` (non-empty list) and optional `version` (must be `1`) and `name`.

Each criterion:

| field | type | notes |
|---|---|---|
| `id` | string, required, unique | |
| `statement` | string, default `""` | human claim; part of the hash |
| `judgment` | bool, default `false` | `true` = needs a human; MUST NOT have a `check` |
| `check` | object | required unless `judgment` |

Unknown fields are an error (a typo must not silently drop an expectation).

### Checks

Common: `expect_contains` and `expect_not_contains` (string or list of strings; case-sensitive substring match).

* `command` (type may be omitted if `cmd`/`argv` is present). Exactly one of `cmd` (string run through the platform shell) or `argv` (list, no shell). `cwd` (default `.`, relative to the criteria file's directory), `timeout` (integer seconds, default 60), `expect_exit` (integer, default 0). Text checks run on stdout followed by stderr.
* `file_contains`: `path` (relative to the criteria file's directory); needs at least one text expectation. A missing file FAILS the check.
* `http`: `url`, `method` (default `GET`, upper-cased), `timeout` (default 30), `expect_status` (integer, default 200); text checks run on the body.

All numbers MUST be integers.

## 2. Observations and evaluation

Running a check yields a raw *observation*:

* command: `{"exit": int, "output": str}` (for `cmd`, a shell exit of 127 or 126 is evaluated as `error`, see below)
* file_contains: `{"content": str}` or `{"missing": true}`
* http: `{"status": int, "body": str}`
* any: `{"error": str}` when the check could not be run (cannot spawn, timeout, network failure, unreadable file).

Evaluation turns an observation into a status:

* `error` if the observation is an error;
* `error` if the check is a `command` written with `cmd` (shell form), the observed exit is 127 or 126, and `expect_exit` is not that same status. A POSIX shell reports a command it cannot find as 127 and one it cannot execute as 126; neither has run the thing under test. The detail says why (`shell could not find the command (exit 127)` / `shell could not execute the command (exit 126)`). If `expect_exit` equals the observed 127 or 126, this rule does not apply and evaluation continues as below, so the check can pass. A check written with `argv` (no shell) is exempt: its 127/126 is the program's own status and is `failed` when it differs from `expect_exit`. Only POSIX shells are covered; Windows `cmd.exe` is out of scope and its codes are not special-cased;
* otherwise `failed` if the exit/status differs from the expectation, the file is missing, an `expect_contains` text is absent, or an `expect_not_contains` text is present;
* otherwise `passed`.

`error` is never evidence of failure: a command that timed out or does not exist (shell exit 127, or 126 if not executable, per the rule above) has not demonstrated the bug.

## 3. Normalisation and hash

Before hashing (and before use) a criterion is normalised: all defaults filled in (`statement ""`, `judgment false`, `cwd "."`, `timeout`, `expect_exit`, `expect_status`, `method`), `expect_*` coerced to lists, a missing `type` inferred as `command`. A judgment criterion normalises to `{"id","statement","judgment":true,"check":null}`.

`hash = sha256_hex( canonical_json(normalised_criterion) )`, where canonical JSON has object keys sorted lexicographically (recursively), no insignificant whitespace, and non-ASCII characters emitted raw (UTF-8). Spelling a default explicitly does not change the hash; changing the `id`, `statement`, or any check field does.

## 4. Lockfile (`.failfirst.lock.json`)

```json
{"failfirst_lock": 1, "created_at": "2026-01-01T00:00:00Z",
 "criteria": {"C1": {"hash": "...", "judgment": false,
                     "baseline": {"status": "failed", "detail": "exit 1, expected 0"}}}}
```

Baseline status is `failed`, `passed`, `error`, or `n/a` (judgment). The lockfile is meant to be committed.

## 5. Protocol

### `baseline`

Run before the work, on the unfixed state. Refuses (exit 2) to overwrite an existing lockfile unless forced: re-baselining after the fix would erase the evidence. Evaluates every non-judgment criterion, writes the lockfile, and exits 0 only if there is at least one non-judgment criterion and all of them `failed`. Criteria that `passed` are **vacuous**; `error` ones are unusable. Either makes the exit code 1 (the lockfile is still written).

### `verify`

Run after the work. Per-criterion verdicts, in order of precedence:

| verdict | condition |
|---|---|
| `awaiting_review` | `judgment: true`. Never auto-passed. |
| `unbaselined` | id not in lockfile (added after baseline) |
| `modified` | hash differs from lockfile (or it was a judgment at baseline). **The goalpost rule.** |
| `vacuous` | baseline status `passed`. Counts for nothing, even if it passes now. |
| `baseline_error` | baseline status `error` |
| `proven` | baseline `failed`, unchanged, passes now |
| `still_failing` | baseline `failed`, unchanged, fails now |
| `error` | baseline `failed`, unchanged, now errored |
| `removed` | in the lockfile, absent from the file now (reported in addition to the listed criteria) |

Any verdict other than `awaiting_review` and `proven` makes the run fail. Overall status:

* `fail`: any non-`proven` machine verdict, or zero machine criteria (judgment alone can never pass);
* `awaiting_review`: all machine criteria `proven` and at least one judgment criterion;
* `pass`: all machine criteria `proven`, no judgment criteria.

Verify only runs checks of criteria that are baseline-`failed` and unchanged.

## 6. Exit codes

`0` pass / baseline ok; `1` fail / baseline has vacuous or errored criteria; `2` usage, malformed criteria, missing or invalid lockfile, refused overwrite; `3` awaiting human review.

## 7. JSON report

```json
{"tool":"failfirst","version":"0.1.1","phase":"verify","status":"pass|fail|awaiting_review",
 "exit_code":0,"summary":{"proven":2},
 "criteria":[{"id":"C1","statement":"...","judgment":false,"verdict":"proven","reason":"...",
              "baseline":{"status":"failed","detail":"..."},"now":{"status":"passed","detail":"ok"}}]}
```

The baseline report has `phase:"baseline"`, `status` `ok|warning`, a `summary` of `failed_as_required / vacuous / errored / judgment`, and per-criterion `baseline` and `vacuous` fields. The human summary format is not normative.

## 8. Conformance vectors

`conformance/protocol.json`: each vector gives `criteria`, optional `verify_criteria` (the file as edited after baseline), `baseline_observations` and `verify_observations` (id to observation), and `expected` (`baseline_exit_code`, `verdicts`, `status`, `exit_code`); plus one `evaluate` vector of single observations. `conformance/hashes.json`: criterion plus expected hash.

## 9. Agent interface (not part of the verdict protocol)

Every implementation also provides: `describe` (tool definitions, Anthropic/OpenAI/MCP, generated from `spec/tools.json`), `mcp` (MCP stdio server, tools `failfirst_baseline` and `failfirst_verify`), `--json` on every command, `--quiet`, and `baseline --dry-run` (run and report, write nothing; the report gains `"dry_run": true`). With `--json`, expected failures print `{"error":{"code","message","hint"}}` on stdout (and a one-line human copy on stderr) and exit 2; the codes and hints are in `spec/tools.json` (`FF_E_USAGE`, `FF_E_NO_CRITERIA`, `FF_E_BAD_CRITERIA`, `FF_E_LOCK_EXISTS`, `FF_E_NO_LOCK`, `FF_E_BAD_LOCK`, `FF_E_IO`; `FF_E_INTERNAL` exits 70). Output shapes: `schemas/`. Vectors: `conformance/agent/`. A command that times out has its whole process tree killed.
