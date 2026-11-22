# Deviation D1 to failfirst-swebench-indep

Filed before any label was joined to any verdict; analyze.py has not been run. The frozen
pre-registration (experiments/failfirst_ext, PREREG.sha256, PREREG.md sha256 56f2d4099b2d...)
and every file in it are unchanged.

**Deviation D1.** 15 of 2,700 runs are MISSING after the registered retry: 5 (instance, patch)
pairs x 3 checks, listed in dev1_keys.json. Cause: each patch also edits a setup file the
instance image had already modified, so `git apply` refuses the whole patch. (Candidate
selection checked applicability against upstream files at the base commit; execution applies
in the image's /testbed. This mismatch is a defect of the registered procedure, found blind.)
The registered status is BLOCKED and is reported first. Supplementary, for these 15 runs only:
in a fresh container, `git apply`; on failure `patch --batch --fuzz=5 -p1` (the official
harness's final fallback; its middle `git apply --reject` step is omitted because it would
leave the tree half-applied before `patch`). A run counts only if every hunk outside the setup
file is verifiably present afterwards. No completed run is repeated; frozen files and
results.jsonl (sha256 9f93354ab893fd38c77e0651dda60d1e7e15ab3840d67ceec8dd31a8eb1da59a, 2,715
rows) are unchanged. Reported side by side: V1 the registered rule with these runs; V2 with the
affected checks dropped (frozen code); V3 all 15 set green; V4 all 15 not green. If these
verdicts differ, no verdict is claimed.

Consequence stated now: `patch --batch` judges the setup-file hunk as already applied and
reverse-applies it, so these 15 runs execute with that one setup file restored to its
base-commit text while the package installed at image build is untouched (the same thing the
official harness's `patch` fallback does). V3 and V4 bound any effect on the 15 verdicts.
sphinx-10323's patch edits both tox.ini (the listed setup file) and setup.py; the setup.py hunk
stays inside the post-condition, which held in the blind pre-check. The choice of fallback
(and the omission of `--reject`) was made from apply exit codes alone, before any check output
of these runs existed.

## Mechanics (fixed now)
- dev1_runner.py runs each pre-listed run once (attempt 3) with the frozen box_runner.py,
  replacing only the in-container apply step; rows go to dev1_results.jsonl, never to
  results.jsonl. It refuses if results.jsonl differs from the hash above, if the incomplete
  runs differ from the 15 keys, or if dev1_results.jsonl already has rows.
- Order: (1) this file and its hashes are published to the public repo; (2) the 15 runs;
  (3) the registered oracle audit completes; (4) the frozen analyze.py runs on the untouched
  data and writes the registered output (evidence/failfirst_ext.json); (5) dev1_analyze.py
  writes evidence/failfirst_ext_dev1.json with V1-V4 and the robustness rule.
- dev1_analyze.py waives only the 15 pre-listed "attempt 3 exceeds the registered single
  retry" lines (V1, V3, V4) or only the missing-verdicts line (V2); every other integrity rule
  of the frozen analysis applies unchanged.

## Blind pre-checks done before filing (no check script executed, no label read)
- In a fresh container, `git apply` fails and `patch --batch --fuzz=5 -p1` exits 0 for all 5
  pairs ("Reversed (or previously applied) patch detected! Assuming -R" for the setup file
  only); every non-setup hunk is present afterwards in all 5.
- None of the 15 affected check scripts mentions pyproject, tox.ini, setup.py or setup.cfg.

## Also reported
- Which apply step succeeded per run and the post-condition result (dev1_results.jsonl).
- Official-harness (swebench 4.1.0) label agreement for the 5 pairs, under a separate run id,
  outside the registered 120-pair audit.
- Blindness is asserted, not provable: the 15 checks' unfixed exit codes exist in
  results.jsonl and labels are in the public lock; nobody joined them before this filing.
- Known: frozen PREREG.md line 3 still reads "Status: DRAFT, not frozen"; the freeze is
  PREREG.sha256 at commit b35ba5e and the public hash at github.com/pallav0107/failfirst 1ea2a7d.
