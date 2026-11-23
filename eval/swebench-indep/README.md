# failfirst on SWE-bench Verified: plan, deviation, run data, analysis

Materials behind the section "A Preregistered Test on Other People's Code" of an
article on fail-first acceptance (under review).

Result. Under the registered rule the verdict is BLOCKED: 15 runs were still missing after
the registered retry. Under deviation D1 (below) the verdict is AGAINST the registered
10-point practical threshold: on 100 instances and 300 model-written checks, fail-first cut
the false-green share by 3.0 points, and checks that failed first still accepted 25% of
runs on wrong patches. Failing first is a floor, not a guarantee.

- `experiments/failfirst_ext/PREREG.md`: the frozen plan. Its hash, `PREREG.sha256`, was
  published at github.com/pallav0107/failfirst (prereg/) before the first run.
- `experiments/failfirst_ext_dev1/DEVIATION.md`: deviation D1 for the 15 runs whose patch
  would not apply. It was published with its hashes before any label was joined.
- `experiments/failfirst_ext*/`: generation, execution, labeling and analysis scripts.
  `analyze.py` is the frozen, registered analysis.
- `experiments/failfirst_ext_explore/explore_gold.py`: an EXPLORATORY reference-fix
  analysis, NOT PREREGISTERED, run after the outcomes were known. It refuses to run
  unless it reproduces V1 exactly.
- `evidence/failfirst_ext_run/`: the model-written checks (`checks/`), the generations,
  per-run results, labels and the oracle audit.
- `evidence/failfirst_ext*.json`: outputs of the analyses.

Third-party patches are identified by SWE-bench submission and instance id and are not
redistributed. SWE-bench is MIT-licensed. The checks were written by a model from issue
text and may contain placeholder addresses under reserved domains (example.com).
