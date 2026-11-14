# Using failfirst with an agent harness

The point: the agent that does the work must not be able to define "done" after seeing the work.

## Loop

1. **Author criteria first**, before any code changes: `failfirst.yaml` with machine checks (`command`, `file_contains`, `http`) and `judgment: true` for anything a command cannot decide.
2. **`failfirst baseline`** on the unfixed tree. Read the result:
   * exit 0: every machine criterion fails, so each one can detect the problem. Commit `.failfirst.lock.json`.
   * exit 1: some criterion is **vacuous** (already passes) or **errored**. Fix the criterion (it is measuring nothing) and baseline again with `--force`. Do this before any work, never after.
3. **Let the agent work.** Give it the criteria file as read-only context. Tell it explicitly that editing a criterion invalidates it.
4. **`failfirst verify --json --report failfirst-report.json`** and act on `exit_code`:

| exit | meaning | agent action |
|---|---|---|
| 0 | all proven | done |
| 3 | all proven, judgment pending | hand the `awaiting_review` ids to a human or reviewer |
| 1 | see per-criterion `verdict` | `still_failing`: keep working. `modified`/`removed`/`unbaselined`: the criteria changed, so revert the edit or ask the owner; never re-baseline to make it pass. `vacuous`: criterion was bad; escalate. |
| 2 | bad input or no lockfile | fix the setup |

## Pseudocode

```python
run("failfirst baseline --json")           # before the work
agent.work(goal, criteria="failfirst.yaml")
report = json.loads(run("failfirst verify --json").stdout)
done = report["status"] == "pass"
```

## Rules for harness authors

* Re-baselining after the fix is the one way to cheat the tool. Gate `--force` behind a human, or keep the lockfile in a place the agent cannot write (commit it, or make it read-only in the agent's sandbox).
* Treat a `modified` verdict as an alarm, not a retry condition.
* A "reviewer says it looks fine" is a `judgment` criterion, and judgment can never turn a `fail` into a `pass`.
* In CI use [action.yml](../action.yml): the lockfile is committed on the unfixed commit, and the job runs `failfirst verify` on the PR.
