# failfirst plugin for Hermes Agent

Makes a Hermes `/goal` finish only when acceptance criteria that **failed on the unfixed code**
now pass, and keeps the agent from editing the criteria to get there.

## Install

```
pip install failfirst
hermes plugins install pallav0107/failfirst/adapters/hermes
hermes plugins enable failfirst
```

Or copy this directory to `~/.hermes/plugins/failfirst` and enable it.

## Flow

1. Write criteria (`failfirst.json`, `.yaml` or `.yml`) in your project.
2. On the **unfixed** code, run `/failfirst baseline [criteria]`. It runs
   `failfirst baseline --json` next to the criteria file and writes `.failfirst.lock.json`.
3. If every criterion failed as required, the reply contains exactly one line starting
   `/goal gate add `.
4. Run `/goal <task>`, then **paste that line yourself**. Hermes accepts gates only once a goal
   exists, and the plugin never adds the gate for you (Hermes restricts gate adds to admins on
   messaging platforms, and only you should control the gate). Hermes then iterates until the
   gate passes.

`/goal` starts its first turn immediately, so that turn can end before your gate line arrives.
The plugin's `pre_verify` hook covers the gap: in a protected session, a turn that edited code
cannot end while the criteria are red. The agent is sent back with the failure output, up to
Hermes' `agent.max_verify_nudges` limit (default 3). Exit 3 (judgment criteria awaiting a person)
does not hold the turn.

The gate is one shell command: a Python check that the lockfile's sha256 still equals the value
recorded at baseline, then `failfirst verify <criteria> --lock <lock> --quiet`. Verify exits 0
only when each criterion failed at baseline, passes now, and is byte-identical to its baseline.

Other commands: `/failfirst status` runs the gate and reports; `/failfirst release` drops the
session's protection; `/failfirst help` prints usage. Protection is saved in
`$HERMES_HOME/failfirst/sessions.json` (default `~/.hermes`) and reloaded on start.

Vacuous criteria (already passing) or errored ones are refused: no gate line is printed, and the
partial lockfile is removed so you can fix the criteria and run baseline again.

## What the `pre_tool_call` hook blocks

In a session with protection only:

- `write_file` / `patch` whose path is the criteria file or the lockfile (relative paths are
  resolved against the recorded cwd), and V4A patch text naming either after `*** Update File:`,
  `*** Add File:`, `*** Delete File:` or `*** Move to:`.
- `terminal` commands that run `failfirst baseline`, or that mention the criteria or lock
  (absolute, relative or basename) together with a write or delete: `>`/`>>`, `rm`, `mv`, `cp`,
  `tee`, `truncate`, `sed -i`, `perl -i`, `chmod`, `git checkout/restore/rm`, `dd of=`, or an
  inline `python -c` / `perl -e` that writes.
- `execute_code` whose code names the criteria or lock and writes, deletes or renames a file.

Reads (`cat`, `grep`, `head`), `failfirst verify` and unrelated work are allowed. The block
message tells the agent to fix the code, not the criteria; a human can run `/failfirst release`.

## Judgment criteria

A criterion marked `judgment: true` needs a person. `failfirst verify` exits 3 for it, so the gate
stays red and Hermes pauses for a human instead of declaring the goal done.

## Limitations

- The hook is a speed bump, not a sandbox: a determined agent can edit files by routes the hook
  cannot see. The real guards are failfirst's per-criterion hashes and the gate's pinned lock
  hash. Only you can change those, because only you edit goal gates: if the criteria or lock
  change, the gate fails regardless of what the hook allowed.
- failfirst hashes the criteria, not the files a criterion runs. If a criterion runs
  `pytest tests/test_x.py`, the agent can still weaken `tests/test_x.py`. Put the assertion in
  the criterion itself, or review the diff of the test files before accepting the goal.
- The gate is a POSIX shell command (Linux, macOS, WSL). Native Windows `cmd.exe` is not
  supported.
- Protection is per session. Run `/failfirst baseline` in a chat that already has a session
  (send one message first); it refuses otherwise. It follows the conversation across context
  compression once the agent has made one tool call after the baseline.
- `/failfirst baseline` never overwrites an existing lockfile. If one from a finished task is in
  the way, delete it yourself and baseline again on the unfixed code.

## Tests

From this directory, with `failfirst` on `PATH`:

```
python -m unittest discover -s tests
```
