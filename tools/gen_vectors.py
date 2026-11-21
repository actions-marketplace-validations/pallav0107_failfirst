import json, sys
sys.path.insert(0, "python/src")
from failfirst import normalize_criteria, criterion_hash

def cmd(i, **kw): 
    return {"id": i, "statement": f"{i} holds", "check": dict({"type": "command", "cmd": "run-" + i}, **kw)}
FAIL = {"exit": 1, "output": "boom"}
OK = {"exit": 0, "output": "ok"}
def vec(name, crit, b, v, exp, vcrit=None, bexit=0):
    d = {"name": name, "criteria": crit, "baseline_observations": b, "verify_observations": v,
         "expected": dict(exp, baseline_exit_code=bexit)}
    if vcrit is not None: d["verify_criteria"] = vcrit
    return d
J = {"id": "J1", "statement": "reads well", "judgment": True}
vs = [
 vec("proven_basic", [cmd("A")], {"A": FAIL}, {"A": OK}, {"verdicts": {"A": "proven"}, "status": "pass", "exit_code": 0}),
 vec("vacuous_passed_at_baseline", [cmd("A")], {"A": OK}, {"A": OK}, {"verdicts": {"A": "vacuous"}, "status": "fail", "exit_code": 1}, bexit=1),
 vec("mixed_proven_and_vacuous", [cmd("A"), cmd("B")], {"A": FAIL, "B": OK}, {"A": OK, "B": OK},
     {"verdicts": {"A": "proven", "B": "vacuous"}, "status": "fail", "exit_code": 1}, bexit=1),
 vec("still_failing", [cmd("A")], {"A": FAIL}, {"A": FAIL}, {"verdicts": {"A": "still_failing"}, "status": "fail", "exit_code": 1}),
 vec("vacuous_even_if_now_failing", [cmd("A")], {"A": OK}, {"A": FAIL}, {"verdicts": {"A": "vacuous"}, "status": "fail", "exit_code": 1}, bexit=1),
 vec("modified_expectation_after_baseline", [cmd("A")], {"A": FAIL}, {"A": OK},
     {"verdicts": {"A": "modified"}, "status": "fail", "exit_code": 1}, vcrit=[cmd("A", expect_exit=1)]),
 vec("modified_statement_after_baseline", [cmd("A")], {"A": FAIL}, {"A": OK},
     {"verdicts": {"A": "modified"}, "status": "fail", "exit_code": 1},
     vcrit=[{"id": "A", "statement": "weaker claim", "check": {"type": "command", "cmd": "run-A"}}]),
 vec("modified_command_after_baseline", [cmd("A")], {"A": FAIL}, {"A": OK},
     {"verdicts": {"A": "modified"}, "status": "fail", "exit_code": 1},
     vcrit=[{"id": "A", "statement": "A holds", "check": {"type": "command", "cmd": "true"}}]),
 vec("explicit_defaults_do_not_modify", [cmd("A")], {"A": FAIL}, {"A": OK},
     {"verdicts": {"A": "proven"}, "status": "pass", "exit_code": 0},
     vcrit=[{"id": "A", "statement": "A holds", "check": {"type": "command", "cmd": "run-A", "cwd": ".", "timeout": 60, "expect_exit": 0, "expect_contains": [], "expect_not_contains": []}}]),
 vec("removed_criterion", [cmd("A"), cmd("B")], {"A": FAIL, "B": FAIL}, {"A": OK},
     {"verdicts": {"A": "proven", "B": "removed"}, "status": "fail", "exit_code": 1}, vcrit=[cmd("A")]),
 vec("added_criterion_unbaselined", [cmd("A")], {"A": FAIL}, {"A": OK, "B": OK},
     {"verdicts": {"A": "proven", "B": "unbaselined"}, "status": "fail", "exit_code": 1}, vcrit=[cmd("A"), cmd("B")]),
 vec("judgment_never_auto_passes", [cmd("A"), J], {"A": FAIL}, {"A": OK},
     {"verdicts": {"A": "proven", "J1": "awaiting_review"}, "status": "awaiting_review", "exit_code": 3}),
 vec("judgment_does_not_rescue_failure", [cmd("A"), J], {"A": FAIL}, {"A": FAIL},
     {"verdicts": {"A": "still_failing", "J1": "awaiting_review"}, "status": "fail", "exit_code": 1}),
 vec("only_judgment_cannot_pass", [J], {}, {},
     {"verdicts": {"J1": "awaiting_review"}, "status": "fail", "exit_code": 1}, bexit=1),
 vec("baseline_error_is_not_a_failure", [cmd("A")], {"A": {"error": "timeout"}}, {"A": OK},
     {"verdicts": {"A": "baseline_error"}, "status": "fail", "exit_code": 1}, bexit=1),
 vec("verify_error", [cmd("A")], {"A": FAIL}, {"A": {"error": "timeout"}},
     {"verdicts": {"A": "error"}, "status": "fail", "exit_code": 1}),
 vec("fails_by_output_text_then_passes", [cmd("A", expect_contains="READY")],
     {"A": {"exit": 0, "output": "starting"}}, {"A": {"exit": 0, "output": "READY now"}},
     {"verdicts": {"A": "proven"}, "status": "pass", "exit_code": 0}),
 vec("file_contains_missing_then_present",
     [{"id": "F", "statement": "file has fix", "check": {"type": "file_contains", "path": "x.txt", "expect_contains": "fixed"}}],
     {"F": {"missing": True}}, {"F": {"content": "this is fixed"}},
     {"verdicts": {"F": "proven"}, "status": "pass", "exit_code": 0}),
 vec("http_status_then_ok",
     [{"id": "H", "statement": "health ok", "check": {"type": "http", "url": "http://x/health", "expect_contains": "up"}}],
     {"H": {"status": 503, "body": "down"}}, {"H": {"status": 200, "body": "up"}},
     {"verdicts": {"H": "proven"}, "status": "pass", "exit_code": 0}),
]
ev = {"name": "evaluate_rules", "criteria": [
  cmd("C1", expect_contains=["a", "b"], expect_not_contains="bad"),
  cmd("C2", expect_exit=3),
  {"id": "F1", "check": {"type": "file_contains", "path": "p", "expect_not_contains": "TODO"}},
  {"id": "H1", "check": {"type": "http", "url": "http://x", "expect_status": 204}},
  cmd("S1"),
  cmd("S2", expect_exit=127),
  {"id": "S3", "check": {"type": "command", "argv": ["run-S3"]}}],
 "evaluate": [
  {"id": "C1", "observation": {"exit": 0, "output": "a b"}, "status": "passed"},
  {"id": "C1", "observation": {"exit": 0, "output": "a"}, "status": "failed"},
  {"id": "C1", "observation": {"exit": 0, "output": "a b bad"}, "status": "failed"},
  {"id": "C1", "observation": {"exit": 1, "output": "a b"}, "status": "failed"},
  {"id": "C1", "observation": {"error": "timeout"}, "status": "error"},
  {"id": "C2", "observation": {"exit": 3, "output": ""}, "status": "passed"},
  {"id": "C2", "observation": {"exit": 0, "output": ""}, "status": "failed"},
  {"id": "F1", "observation": {"content": "clean"}, "status": "passed"},
  {"id": "F1", "observation": {"content": "a TODO"}, "status": "failed"},
  {"id": "F1", "observation": {"missing": True}, "status": "failed"},
  {"id": "H1", "observation": {"status": 204, "body": ""}, "status": "passed"},
  {"id": "H1", "observation": {"status": 200, "body": ""}, "status": "failed"},
  {"id": "H1", "observation": {"error": "refused"}, "status": "error"},
  {"id": "S1", "observation": {"exit": 127, "output": "sh: 1: run-S1: not found"}, "status": "error"},
  {"id": "S1", "observation": {"exit": 126, "output": "sh: 1: run-S1: Permission denied"}, "status": "error"},
  {"id": "S2", "observation": {"exit": 127, "output": ""}, "status": "passed"},
  {"id": "S2", "observation": {"exit": 126, "output": ""}, "status": "error"},
  {"id": "S3", "observation": {"exit": 127, "output": ""}, "status": "failed"},
  {"id": "S3", "observation": {"exit": 126, "output": ""}, "status": "failed"}]}
hs = []
for name, c in [("hash_command_defaults", {"id": "A", "statement": "A holds", "check": {"cmd": "pytest -q"}}),
                ("hash_unicode_and_order", {"statement": "héllo → 世界 \"q\"", "id": "U", "check": {"expect_contains": ["é", "x"], "type": "command", "argv": ["echo", "é"]}}),
                ("hash_judgment", {"id": "J", "judgment": True, "statement": "looks right"}),
                ("hash_file_contains", {"id": "F", "check": {"type": "file_contains", "path": "a/b.txt", "expect_contains": "x"}}),
                ("hash_http", {"id": "H", "check": {"type": "http", "url": "http://x/", "method": "get"}})]:
    hs.append({"name": name, "criterion": c, "hash": criterion_hash(normalize_criteria([c])[0])})
json.dump({"description": "Protocol vectors: baseline then verify with simulated observations.", "vectors": vs + [ev]}, open("conformance/protocol.json", "w"), indent=2, ensure_ascii=False)
json.dump({"description": "Content-hash vectors: canonical JSON of the normalised criterion, sha256 hex.", "vectors": hs}, open("conformance/hashes.json", "w"), indent=2, ensure_ascii=False)
