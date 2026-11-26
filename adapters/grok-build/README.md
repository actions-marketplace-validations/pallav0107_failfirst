# failfirst for Grok Build

An adapter for [Grok Build](https://x.ai) (xAI's terminal coding agent, the `grok` CLI; written against 1.0.92). It makes a Grok session unable to finish while the failfirst acceptance criteria are still unproven, and keeps the agent from editing the criteria or the lockfile.

One file, standard library only: `failfirst_grok.py` (Python 3.9+, POSIX shell).

## Install

```
npm install -g @xai-official/grok      # or xAI's installer
pip install failfirst
python3 failfirst_grok.py install-hooks
```

`install-hooks` writes `$GROK_HOME/hooks/failfirst.json` (`GROK_HOME` defaults to `~/.grok`) with a PreToolUse hook (timeout 15 s) and a Stop hook (timeout 600 s, because Grok's 5 s default would kill a verify run). Re-running it is safe.

## Flow

1. Write your criteria (`failfirst.json`) in the project.
2. On the **unfixed** code, run `python3 failfirst_grok.py baseline`. It runs `failfirst baseline`, refuses (exit 1, no record, no lockfile left behind) if any criterion is vacuous, that is, already passes, or errored, and otherwise records the criteria path and the lockfile's sha256 in `$GROK_HOME/failfirst/workspaces.json`.
3. Either:
   * `python3 failfirst_grok.py run -- "<task>"`: runs `grok -p` headless, then `failfirst verify`; if still red it continues the session (`-c`) with the failure output, up to `--max-rounds` (default 3). Exit 0 proven, 3 judgment criteria await a human, 1 still red, 2 no baseline. Options: `--model M`; the binary is `$FAILFIRST_GROK_BIN` or `grok` on PATH.
   * or just use `grok` interactively with the hooks installed.

Other commands: `status` (run the gate for this directory, exit with its code) and `release` (drop this directory's record; a human does this when the criteria are genuinely wrong).

## What the hooks do

* **PreToolUse**: when the workspace has a record, denies (`{"decision":"deny"}`, exit 2) `write` / `search_replace` onto the criteria file or lockfile, and `run_terminal_command` calls that run `failfirst baseline` or write, delete, move, chmod or `git checkout`/`restore` the criteria or lockfile (`>`, `>>`, `rm`, `mv`, `cp`, `tee`, `truncate`, `sed -i`, `perl -i`, `dd of=`, `python -c` writes, ...). Reads and `failfirst verify` are allowed. Any internal error allows the call.
* **Stop**: when the agent stops with reason `end_turn`, checks that the lockfile still matches the recorded sha256, then runs `failfirst verify`. Red: it blocks the stop (`{"decision":"block"}`, exit 2) and names each unproven criterion with what its check runs or looks for, so the agent knows what is still missing. After `FAILFIRST_GROK_MAX_STOP_BLOCKS` (default 5) consecutive blocks for one session it lets the agent stop. Proven (0) or awaiting a human (3) resets the counter and allows the stop. Other stop reasons, such as shutdown, are never blocked.

## Stop blocking is undocumented

xAI's documentation describes the Stop hook as passive. A Stop hook that returns `{"decision":"block"}` with exit 2 and keeps the agent working is **undocumented** behaviour, measured on grok 1.0.92; a later version may change it. Grok also fails open on hook errors and timeouts. So the hooks are a convenience, and `failfirst_grok.py run`'s final `failfirst verify` is the guarantee: use it when the result matters.

## Limits

* The PreToolUse hook is a speed bump. A determined agent can write the criteria through a route the patterns do not recognise. The real guard is that failfirst hashes the criteria and the lockfile hash is pinned at baseline, so a changed criterion or lock turns the gate red.
* failfirst hashes the criteria, not the test files the criteria run. An agent that edits a test file the check calls can still weaken it; keep checks self-contained or review those files.
* POSIX shell only; the shell-command patterns assume sh syntax.
* The adapter's own state (`$GROK_HOME/failfirst/`) is not guarded by the hook. `run` reads the record before starting Grok, so editing that state cannot make `run` report green.
* `run` continues with `grok -c`, the most recent session in the directory. Do not run a second Grok session in the same directory at the same time.

Measured end to end on grok 1.0.92 with a local model (`gpt-oss:20b` via Ollama): with the criteria file kept outside the repo, so the agent could not read it in advance, the Stop hook told the agent that the changelog check still failed. The agent added the entry and `run` reported PROVEN after one round.

## Local models

Grok Build accepts custom models in `$GROK_HOME/config.toml`, so the loop works with a local server, for example Ollama:

```toml
[model.local]
base_url = "http://127.0.0.1:11434/v1"
api_key = "ollama"
api_backend = "chat_completions"
model = "qwen3-coder"
```

Select it with `grok -m local`, or `failfirst_grok.py run --model local -- "<task>"`.

## Tests

```
cd adapters/grok-build && python3 -m unittest discover -s tests
```

They need the `failfirst` CLI on PATH and use a temporary `GROK_HOME` and a fake `grok`.
