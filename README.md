# failfirst

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24486276.svg)](https://doi.org/10.5281/zenodo.24486276)

> A check that has never failed carries no information.

`failfirst` makes acceptance criteria prove themselves. A criterion only counts as passing after a change if it was first **shown to fail on the unfixed code**, and has not been edited since.

It is built for AI-agent loops and CI, where "done" is too often declared on the strength of a test that was never able to fail: a vacuous assertion, a command that always exits 0, a threshold quietly lowered until the run went green.

## The idea

```
failfirst baseline   # BEFORE the work: run criteria on the unfixed state, write .failfirst.lock.json
   ... agent / human changes the code ...
failfirst verify     # AFTER: a criterion counts only if it
                     #   (a) FAILED at baseline,
                     #   (b) PASSES now, and
                     #   (c) is byte-for-byte the same criterion as at baseline
```

Criteria are plain JSON or YAML:

```yaml
criteria:
  - id: add-works
    statement: add(2, 3) returns 5
    check: { cmd: 'python3 -c "from calc import add; assert add(2,3)==5"' }
  - id: changelog
    check: { type: file_contains, path: CHANGELOG.md, expect_contains: "fix: add()" }
  - id: reads-well
    statement: the diff is minimal and clear
    judgment: true        # never auto-passed; reported as awaiting human review
```

Check types: `command` (exit code, output contains / not contains), `file_contains`, `http`.

## The anti-goalpost-moving rule

Each criterion is content-hashed at baseline. Edit it afterwards (weaken the assertion, change the command, rewrite the statement, loosen the exit code) and `verify` reports it **modified** and fails. Delete it: **removed**. Add a new one: **unbaselined**, since it never had a chance to fail. A criterion that already **passed at baseline is vacuous** and counts for nothing, even if it still passes. Re-running `baseline` refuses to overwrite the lockfile (that would erase the evidence) unless you pass `--force`.

Timeouts and "cannot start" are `error`, never accepted as a failure: a command that does not exist has not demonstrated your bug.

## Exit codes

`0` pass, `1` fail (or baseline found vacuous/errored criteria), `2` usage or invalid input, `3` all machine criteria proven but judgment criteria await a human.

## Install and use

Two interchangeable implementations of one [spec](spec/SPEC.md), both passing the shared [conformance vectors](conformance/):

```
pip install failfirst               # python/   (needs PyYAML for YAML files)
npm i -g @pallav0107/failfirst      # js/       (the unscoped npm name is taken)
failfirst baseline
failfirst verify --json
```

Try the self-demo: `FAILFIRST=failfirst examples/demo.sh`.

Other docs: [spec/SPEC.md](spec/SPEC.md), [use with your agent harness](docs/AGENT_HARNESS.md), [action.yml](action.yml) (GitHub Action).

## Agent use

Built for agents to call without help: [`llms.txt`](llms.txt) and [`AGENTS.md`](AGENTS.md) (exact commands, exit codes, examples, pitfalls; shipped inside both packages).

* `failfirst describe --json` prints tool definitions in Anthropic, OpenAI and MCP formats, all generated from one file, [`spec/tools.json`](spec/tools.json).
* `failfirst mcp` serves `failfirst_baseline` and `failfirst_verify` over MCP stdio.
* Every command takes `--json`; the output shapes are the JSON Schemas in [`schemas/`](schemas/). `--quiet` gives one line (or compact JSON), `baseline --dry-run` writes nothing.
* Failures are `{"error": {"code", "message", "hint"}}` with stable `FF_E_*` codes and exit 2. Nothing prompts, reads stdin or prints ANSI colour.
* `eval/run_agent_eval.py` is the agent task eval (scripted tasks in `eval/agent_tasks/`; needs an OpenAI-compatible endpoint).
* [`eval/swebench-indep/`](eval/swebench-indep/) is the preregistered test of fail-first on SWE-bench Verified (plan hash in [`prereg/`](prereg/)): plan, deviation, model-written checks, run data and analysis. Under the registered rule it is BLOCKED; under deviation D1, fail-first removed vacuous checks, but checks that failed first still accepted 25% of runs on wrong patches.

## Hermes Agent

[`adapters/hermes/`](adapters/hermes/) is a plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent). `/failfirst baseline` records the criteria failing on the unfixed code and prints a `/goal gate add` line, so a Hermes `/goal` cannot finish until those criteria pass. A `pre_tool_call` hook stops the agent editing the criteria or the lockfile, or re-running the baseline, while the goal runs.

## What it is not

* Not a test framework. It runs whatever commands you give it and judges exit codes and text.
* Not a sandbox or a security boundary: criteria are commands and run with your privileges. An agent that can edit both the code and the criteria file is only caught on the criteria it edits; protect the lockfile and criteria file (commit the lock before the work, review criteria changes) if your agent is untrusted.
* Not proof the fix is *right*, only that the criteria were capable of failing and now pass. Bad criteria that fail for the wrong reason still prove nothing about the right one; the `judgment` type exists for what a command cannot decide.
* Not mutation testing. It proves a criterion failed once, on the state you pointed it at.

## Citing

failfirst 0.1.2, including the SWE-bench Verified test in `eval/swebench-indep/`, is archived on Zenodo: [doi:10.5281/zenodo.24486276](https://doi.org/10.5281/zenodo.24486276).

## License

MIT. Copyright (c) 2026 Pallav Pokhriyal.
