# Pre-registration: does a fail-first filter on agent-written checks reduce false greens on SWE-bench Verified?

Task id: `failfirst-swebench-indep`. Status: DRAFT, not frozen. The freeze is the commit that adds
`PREREG.sha256`, written by `python freeze.py`: the sha256 of EVERY file in this folder (this file,
`prompt.txt`, `sample.lock.json`, the id lists, all code including `box/` and `tests/`, and
`.gitattributes`; caches excluded). The hash file is published to a public repository before any
check is generated or executed on a sampled instance. Once `PREREG.sha256` exists, `analyze.py`,
`generate.py`, `run_checks.py bundle` and `audit_oracle.py prepare` refuse to run if any frozen
file differs or any unfrozen file is present, and the sampled-run tools also refuse a lock whose
bytes differ from the frozen `sample.lock.json`.

## Hypothesis

When an LLM writes acceptance checks for a bug from the issue text alone, some checks already pass on
the unfixed code ("vacuous" checks). Such a check accepts almost any candidate patch, including wrong
ones. Keeping only the checks that are observed to FAIL on the unfixed code (fail-first) should lower
the share of accepted ("green") patches that are in fact wrong.

H1: D = FGS_A - FGS_B (false-green share of the unfiltered arm A minus that of the fail-first arm
B) is credibly above 0, with a point estimate of at least 10 percentage points, and above the
instance-stratified placebo null. This is exactly what the SUPPORTED rule tests; it does not claim
that the true reduction is at least 10 pp (the CI lower bound is only required to exceed 0).

The near-tautological part is stated up front: a check that passes on unfixed code passes on nearly
every patch, so removing such checks lowers the false-green share whenever they exist. The empirical
content is (a) how often an issue-only, single-shot check-writer produces vacuous checks, and (b) how
many false greens REMAIN after the filter (S2). Fail-first is claimed to be necessary, not sufficient.

## Dataset and sampling

- Instances: SWE-bench Verified (`princeton-nlp/SWE-bench_Verified`, revision
  `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, parquet sha256
  `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`; ids in `verified_ids.txt`).
- Pilot exclusion: the 22 instances in `pilot_ids.txt` (images present before sampling) are used only
  for the pilot and are removed from the frame (478 instances remain).
- Candidate patches and oracle labels: third-party submissions in `github.com/SWE-bench/experiments`,
  directory `evaluation/verified/`, pinned commit `40f164d5b8f1d249bf95a6df8b74b577fd8e519d`. The pool
  is every submission whose `results/results.json` has a `resolved` list and whose `metadata.yaml`
  names an `s3://` logs bucket (125 of the 182 entries; the other 57 lack one of the two files at the
  pinned commit or name no bucket).
- Labels. `resolved` = listed in `resolved`. `unresolved` = a Verified instance not in `resolved`,
  not in any harness-failure list present in that file (`no_generation`, `no_logs`, `no_apply`,
  `install_fail`, `reset_failed`, `test_errored`, `test_timeout`), inside `generated`/`with_logs` when
  those lists exist, AND with evidence in the submission's own per-instance `report.json` (same logs
  bucket) that the tests really ran: `patch_successfully_applied` is true, `tests_status` is present,
  at least one FAIL_TO_PASS test is listed, and at least one FAIL_TO_PASS or PASS_TO_PASS test passed.
  A candidate without such a report is ineligible (`no_report_evidence`). Consequence: an unresolved
  patch that breaks every test (for example an import error) is excluded; such patches would be easy
  to reject, so the exclusion makes the unresolved set harder, not easier.
- Order: `random.Random(20261123).shuffle(sorted(frame))`, walked in that order.
- Inclusion: an instance is included when 3 resolved and 3 unresolved eligible patches are found
  that are non-empty, not a member of a label-conflicting identity group (below), pairwise distinct
  after whitespace normalisation (touched file names plus added/removed lines with all whitespace
  removed) and accepted by `git apply --check` at the base commit. Submissions are tried per instance in ascending order of
  `sha256("20261123:" + instance_id + ":" + submission)`; the first 3 eligible of each label are
  taken. Otherwise the instance is SKIPPED with a logged reason. Walking stops at N included.
  Labels are used at this stage only to balance the patch pool.
- Label-conflicting identity groups: before the walk, EVERY labelled candidate of the instance is
  fetched and grouped by normalised identity. A group whose members carry both published labels
  (the same edit judged both resolved and unresolved) is label noise, and every member of it is
  ineligible (`label_conflict`), whether or not the walk would reach it. The groups are recorded in
  the lock as direct label-noise evidence.
- The draw is recorded in `sample.lock.json` (walk order, every tried submission and its outcome, the
  results.json hash of every pool entry, each chosen patch's sha256, selection statistics) and is
  re-derivable with `python sample.py --seed 20261123 --verify sample.lock.json`; `--deep` repeats
  the whole selection against an empty cache (every patch, report and base file downloaded again).
- Images: every included instance's public image must be present on the execution host before the
  freeze. An image the registry reports as absent (status `missing` in the pull log; never
  throttling or a transient error) is recorded with `sample.py --image-failures-from`, which skips
  that instance, and the walk is re-run so the next instance in the seeded order replaces it. This
  path exists only before the freeze; afterwards the tools refuse to change the lock.
- Final draw, 2026-11-22 (same seed and walk throughout): 118 instances walked, 18 skipped (15.3%,
  all for insufficient eligible patches), 100 included, 600 patches, no overlap with the pilot.
  Candidate outcomes over the walk: 668 accepted, 131 patch unavailable, 76 unresolved candidates
  rejected for missing report evidence, 33 not applying, 32 same-label duplicates, 21 rejected as
  members of a label-conflicting group, 1 empty. 23 label-conflicting groups were found in 15 of the
  118 walked instances.
- Supersession chain of `sample.lock.json` (each superseded before any sampled generation or run):
  1. sha256 `b24142d82a04f2bf06c07052b74c8fa90fab8778739f2b56e8375907f5ce3c23` (commit f275681):
     first draw; unresolved labels taken from results.json alone. Superseded because unresolved
     labels could include harness failures.
  2. sha256 `d33d039e09b4c37e6a32029979c25b60b5816fba63c1185b4c3ef76f1392bc8d` (commit f06fc16):
     adds the per-instance report.json evidence rule (3 instances replaced, 35 kept instances
     received a different patch set). Superseded because only the LATER twin of a label-conflicting
     pair was rejected, so the earlier twin (for example in django__django-16145 and
     psf__requests-2317) stayed in the sample.
  3. sha256 `887624de6dc7c9b54a88f4a6cd8d94b0fb29dbcfa4ed63c3ec8b5c8af8c824f1` (final, this freeze):
     every member of a label-conflicting group is ineligible. Same 100 instances as lock 2; 5 of
     them received a different patch set.

## Sample size

N = 100 instances, K = 3 checks each (300 checks), M = 6 candidate patches each (1,800 check-patch
verdict pairs, 600 oracle labels). The owner fixed N = 100 before the freeze.

Precision: a share estimated over 100 clusters has a worst-case 95% half-width of about 10 pp.

Power (`power_sim.py`, 500 replicates per row, 2,000 bootstrap resamples and 200 placebo draws per
replicate, registered decision rule including the placebo-null condition; "clustered" = fail-first
checks of an instance share a latent per-patch "fixes the symptom" flag and type shares vary by
instance). Every simulated row:

| scenario (vacuous / fail-first / error) | model | true D | P(CI low > 0) | P(SUPPORTED) | P(AGAINST) | P(INCONCLUSIVE) |
|---|---|---|---|---|---|---|
| 30% / 45% / 25% (plan) | iid | 0.189 | 1.00 | 1.00 | 0.00 | 0.00 |
| 30% / 45% / 25% (plan) | clustered | 0.188 | 1.00 | 1.00 | 0.00 | 0.00 |
| 10% / 45% / 45% (plan) | iid | 0.106 | 1.00 | 0.72 | 0.00 | 0.28 |
| 10% / 45% / 45% (plan) | clustered | 0.109 | 1.00 | 0.61 | 0.02 | 0.36 |
| 10% / 65% / 25% | iid | 0.084 | 1.00 | 0.12 | 0.23 | 0.65 |
| 10% / 65% / 25% | clustered | 0.083 | 1.00 | 0.12 | 0.26 | 0.61 |
| 8.9% / 45% / 46% (true D = 10 pp) | iid | 0.097 | 1.00 | 0.49 | 0.04 | 0.47 |
| 8.9% / 45% / 46% (true D = 10 pp) | clustered | 0.098 | 1.00 | 0.45 | 0.05 | 0.51 |
| 2% / 73% / 25% (near null) | iid | 0.019 | 0.85 | 0.00 | 1.00 | 0.00 |
| 2% / 73% / 25% (near null) | clustered | 0.019 | 0.78 | 0.00 | 1.00 | 0.00 |

Power to declare SUPPORTED under the 30% scenario is 1.00 (threshold 0.8), so N stays 100. At a true difference of exactly 10 pp the probability of SUPPORTED is about 0.45-0.49 by construction, because the rule also requires the point estimate to reach 10 pp; with only 10% vacuous checks and few erroring ones (true D about 8 pp) it is about 0.12 and the outcome is mostly INCONCLUSIVE. The lower-CI-bound condition alone is weak evidence: it is met in 78-85% of replicates even when the true difference is 2 pp. The 10 pp threshold and the placebo null carry the decision. Limitation of the simulation: an erroring check is never green there, so all simulated D comes from removing vacuous checks; S9 reports the ERROR part of the real D separately.

## Check writer

- Model: `qwen3.7-plus` on the Alibaba Model Studio prepaid token-plan endpoint (OpenAI-compatible
  chat completions). Parameters: temperature 0.7, top_p 0.8, max_tokens 4096, thinking disabled,
  seeds 1, 2, 3 for the three checks of an instance. The `model` field returned by the API is recorded
  for every call; more than one distinct returned string blocks the run.
- Input: repository name, version and `problem_statement` only, through the frozen `prompt.txt`. No
  repository access, no hints, no execution feedback.
- Attempts: each slot gets at most 3 replies: attempt 0 (seed k), and a regeneration only when the
  reply is empty or has no parseable Python script (attempts 1 and 2, seeds 100k+1 and 100k+2).
  Every reply is logged with its attempt number and the sha256 of the extracted script. The check
  file is the first usable reply; `analyze.py` verifies this from the log and blocks otherwise. A slot
  with no usable reply after 3 attempts holds a script that exits 127 (ERROR, never green), counted.
- No local model, no model from the vendors of the paper's other systems, and no metered credential.

## Execution

- Each check runs inside the public SWE-bench instance image (`swebench/sweb.eval.x86_64.*`), from
  `/testbed` in the `testbed` environment, `--network none`, 120 s limit (`timeout -k 5 120`), at most
  6 containers at a time: twice on the unfixed tree, once on each of the 6 candidate patches, once on
  the gold patch (gold is used only for S6). Patches are applied with `git apply` in the container.
- Outcome classes follow the published tool's rule: exit 0 = PASS; exit 126/127 or a timeout inside
  the container (124/137) = ERROR; any other non-zero exit = FAIL. The unfixed outcome is the common
  class of the two unfixed runs; disagreement (flaky) or any ERROR = ERROR.
- Missing rows and rerun rule. A run is COMPLETED only when the exit code was read from the
  in-container marker, docker exited 0, the outer watchdog did not fire and, for a patched tree, the
  patch applied in the container. Anything else (no exit code, docker error, outer watchdog,
  in-container apply failure) is MISSING, never an outcome. A missing run is retried exactly once
  (attempt 2); every attempt is logged with its attempt number and the host's 1-minute load average
  at start and end. The completed attempt is the verdict. More than one completed row for the same
  (check, target), a repeated attempt number, or an attempt number above 2 is a silent rerun and
  BLOCKS the analysis. Any run still missing after the retry BLOCKS (threshold: zero).

## Primary metric

For arm X, FGS_X = (green pairs whose patch is labelled unresolved) / (all green pairs), pooled over
instances (ratio of sums). green(check, patch) = PASS on the patched tree.
Arm A: every check. Arm B: the checks whose unfixed outcome is FAIL. Both arms use the same
generations and the same executions; arm-B membership is a function of the unfixed exit codes only.

Primary: D = FGS_A - FGS_B, with a 95% percentile CI from an instance-cluster bootstrap
(10,000 resamples; resample indices from Python `random.Random(20261123)`). Resamples where D is
undefined (no green pair in an arm) are dropped and their count is reported. D depends on the 3+3
resolved/unresolved split of the patch pool (it is a share among greens); FPR and TPR below do not.

## Secondary metrics

Descriptive, no significance claims; all are reported whatever the verdict, none is decision-bearing
except S1's upper bound inside the AGAINST rule.
- S1 vacuous share: checks with unfixed outcome PASS / all checks (with cluster-bootstrap CI), and
  the share of instances where all 3 checks are vacuous.
- S2 residual false-green rate: arm-B green pairs on unresolved patches / arm-B pairs on unresolved
  patches. Descriptive and not decision-bearing, because the thesis claims fail-first is necessary,
  not sufficient. A high S2 means fail-first checks still accept many wrong patches: the filter
  removes one failure mode and leaves the check-writer's other errors, which the paper must state.
- S3 cost: share of arm-A greens on resolved patches that arm B keeps; share of instances with no
  fail-first check.
- S4 placebo (see Analysis).
- S5 strict rule: as arm B, but a check counts as failing only if, in both unfixed runs, the last
  traceback on stderr ends in AssertionError and passes through the check's own file.
- S6 comparability with SWT-Bench: share of checks that FAIL unfixed and PASS on the gold patch.
- S7 oracle audit agreement per label; per-repository breakdown; ERROR share.
- S8 per-arm FPR = greens on unresolved / unresolved verdicts and TPR = greens on resolved / resolved
  verdicts (with CIs); independent of the 3+3 split.
- S9 decomposition of D = [FGS_A - FGS_N] + [FGS_N - FGS_B], where N = A minus the PASS-on-unfixed
  checks: the first term is the part from removing vacuous checks, the second the part from removing
  ERROR-on-unfixed checks (flaky, timeout, cannot run).

## Analysis

- Blinding: oracle labels are joined to verdicts only inside `analyze.py`, after the freeze gate,
  after checking that the run manifest was generated with the frozen prompt, and after the
  generation-log cross-check above.
- Placebo (S4), used as a null distribution: 1,000 draws from `random.Random(20261124)`. In each draw
  every instance keeps as many of its own checks, chosen uniformly at random, as arm B keeps in that
  instance (stratified by instance; no resampling), and D_P = FGS_A - FGS_P is computed. Reported:
  mean, 2.5th and 97.5th percentiles. SUPPORTED requires D above the 97.5th percentile.
- Oracle audit: the official SWE-bench harness (swebench 4.1.0) is re-run under one run id on a
  seeded, label-stratified sample: one `random.Random(20261123)` draws 60 of the sorted resolved
  pairs, then 60 of the sorted unresolved pairs (120 of 600). `analyze.py` recomputes this selection
  from the frozen lock and requires the audited pair set to equal it exactly, with n = 120 and 60 per
  label; a pair without a report counts as a disagreement. Agreement is reported per label.
- Completeness: every check has 2 unfixed runs, 6 patch runs and a gold run; any missing verdict, or
  a verdict whose check or patch hash differs from the manifest, is counted as missing.

## Decision rule

Precedence: BLOCKED, then AGAINST, then SUPPORTED, else INCONCLUSIVE.
- BLOCKED (integrity stop, no verdict): oracle audit agreement below 95% for EITHER label (fewer than
  57 of 60), the audited pairs differ from the seeded selection, more than 20% of walked instances
  skipped, more than one distinct returned model string, any verdict missing after the registered
  retry, a silent rerun (duplicate completed row, repeated or out-of-range attempt), or a check file
  that is not the first usable reply of its slot.
- AGAINST: upper CI bound of D < 10 pp, or the CI lies entirely below 0, or the upper CI bound of the
  S1 vacuous share < 5%. AGAINST means "D is below the registered 10 pp practical threshold" (or
  vacuous checks are too rare for the filter to act on); it does not mean "the filter does not help"
  in general.
- SUPPORTED: D credibly above 0, with a point estimate of at least 10 pp, and above the
  instance-stratified placebo null; operationally: lower CI bound of D > 0 AND D >= 10 pp AND
  D > the 97.5th percentile of the placebo D_P.
- INCONCLUSIVE otherwise, including when D is undefined because arm B has no green pair.
All outcomes are reported in the same paragraph and table position, with S2, S8 and S9.

## What would count against the thesis

- D's upper CI bound below 10 pp: the filter does not remove a practically useful share of false
  greens, for example because the check-writer rarely writes vacuous checks.
- D's CI entirely below 0: the filter makes accepted patches less trustworthy.
- S1 upper bound below 5%: the failure the filter targets barely occurs with this check-writer.
- D not above the placebo null: a random filter of the same size does as well.
- Reported regardless: a high residual false-green rate S2.

## Limitations stated now

- Contamination: the check-writer has very likely seen SWE-bench issues, fixes and tests in training.
  Expected direction: better-informed checks, so fewer vacuous checks (S1 biased down, D biased toward
  zero, i.e. against H1) and fewer residual false greens (S2 biased down, i.e. flattering fail-first).
- Unresolved is not wrong: some unresolved patches fix the reported symptom and fail only hidden
  tests; a green on them is a false green by the oracle but not necessarily a wrong check verdict.
- Patch-pool composition (descriptive): report evidence is required for unresolved patches only.
  Unresolved patches excluded for lack of it (for example ones that break every test) would rarely
  be green, so excluding them shrinks FPR denominators and makes the unresolved set harder. Labels
  also split by submission year: resolved patches are mostly from 2025 submissions (227 of 300; 73
  from 2024), unresolved mostly from 2024 (184 of 300; 116 from 2025). Both arms see exactly the same
  patches, so neither feature confounds the arm comparison; they bear on how the absolute FGS, FPR
  and TPR values generalise.
- Representativeness: the frame excludes instances with fewer than 3 eligible resolved or unresolved
  submissions (mid-difficulty bugs only); repository mix of the sample: django 46, sympy 14, matplotlib 8, sphinx 8, astropy 5, pylint 5,
  scikit-learn 5, xarray 5, pytest 2, requests 2 (django 46% vs 46% of Verified).
- Single check-writer model; results do not transfer to other models or to agents with execution.
- Published labels can be flaky; the stratified audit bounds this per label.

## Pilot rule (decided before the freeze, applied mechanically)

Before the freeze, `generate.py --pilot` writes 3 checks for each of the 22 pilot instances with
this `prompt.txt`, and each check is run twice on the unfixed tree and once on the gold patch.
`python analyze.py --pilot-report RUN_DIR` computes broken_share = (checks whose unfixed outcome is
ERROR, or whose two unfixed runs and gold run all end in a Python exception other than
AssertionError) / (checks with all three runs completed). If broken_share > 0.60, the prompt gains
BM25 excerpts and nothing else changes: query = the `problem_statement` lower-cased and split on
non-alphanumerics; documents = every `.py` file of the repository at the base commit outside
directories named `tests`/`test`/`testing`; Okapi BM25 with k1 = 1.2, b = 0.75; the top 3 files by
score (ties by path), first 200 lines each, inserted under the issue as "Possibly relevant files".
If broken_share <= 0.60, `prompt.txt` stays exactly as it is. The pilot result and the outcome of this
rule are entered under Deviations before the freeze.

## Deviations

From the design plan of 2026-11-22, all decided before the freeze and before any sampled run:
1. Check-writer is cloud `qwen3.7-plus` via the prepaid token-plan endpoint, not a local model
   (owner decision, Amendment 1). Generation runs on a separate workstation; only generated check
   files travel to the execution host.
2. Label pool is 125 of 182 submission entries (57 lack `results.json`/`metadata.yaml` at the pinned
   commit or name no logs bucket); unresolved labels additionally need per-instance report evidence.
3. The gold patch is also executed (needed for S6); it is not part of the primary metric.
4. Sampling parameters chosen during the build: temperature 0.7 / top_p 0.8 (temperature 0 would make
   the three seeds near-identical), thinking disabled.
5. Bootstrap uses Python's `random` (reproducible without numpy). The placebo is an
   instance-stratified null and SUPPORTED requires D above its 97.5th percentile (replaces the plan's
   "placebo CI includes 0"). The oracle audit is stratified 60/60 with a per-label threshold.
   Decision-rule precedence made explicit.
6. Execution is split into `run_checks.py` (orchestration), `box/box_runner.py` (executor with the
   registered single retry) and `box/pull_images.sh`, instead of a single `execute.py`.
7. Pilot (2026-11-22, the 22 pilot instances only, before the freeze). Earlier smoke test on 3 of
   them: 0/9 ERROR, 2/9 broken. Full pilot with this `prompt.txt`: 66 generation calls, 66 usable
   replies, 0 regenerations, one returned model string `qwen3.7-plus`, 60,435 input and 80,769 output
   tokens; 198 container runs (2 unfixed + gold per check), 0 missing after the registered retry,
   0 timeouts. Unfixed outcomes: 59 FAIL, 7 PASS, 0 ERROR; unfixed x gold: 28 FAIL/PASS, 31 FAIL/FAIL,
   7 PASS/PASS. `analyze.py --pilot-report`: 20 of 66 checks broken, broken_share 0.303 <= 0.60, so
   the registered rule gives add_bm25 = false and `prompt.txt` is unchanged. No further prompt
   iteration follows, whatever else the pilot shows.
8. Independent methodology reviews (2026-11-22) applied before the freeze. Second review: H1 and
   SUPPORTED restated as exactly what the rule tests (no threshold changed), AGAINST worded as
   "below the 10 pp practical threshold", every member of a label-conflicting group made ineligible
   (lock 3), patch-pool composition stated. First review: freeze covers every file,
   missing-run retry rule, silent-rerun blocks, report evidence for unresolved labels (lock rebuilt
   with the same seed and walk), stratified placebo null, stratified audit, S8/S9, strict S5, the
   contamination and representativeness limitations, and this deterministic pilot rule.
