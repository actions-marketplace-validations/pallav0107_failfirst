"""Oracle audit selection, batching and collection (C8 logic)."""
import json

import audit_oracle as AO


def _insts(n=100):
    return [{"instance_id": f"r__r-{i}",
             "patches": [{"submission": f"s{j}", "label": "resolved" if j < 3 else "unresolved"}
                         for j in range(6)]} for i in range(n)]


def test_selection_is_seeded_20pct_of_600_stratified():
    a = AO.select_pairs(_insts())
    assert len(a) == 120 and a == AO.select_pairs(_insts())
    assert sum(p["label"] == "unresolved" for p in a) == 60
    assert a != AO.select_pairs(_insts(), seed=1)


def test_batches_never_repeat_an_instance():
    pairs = AO.select_pairs(_insts())
    bs = AO.batches(pairs)
    assert sum(len(b) for b in bs) == len(pairs)
    for b in bs:
        ids = [p["instance_id"] for p in b]
        assert len(ids) == len(set(ids))


def test_collect_counts_missing_report_as_disagreement(tmp_path):
    pairs = [{"instance_id": "a__a-1", "submission": "s1", "label": "resolved"},
             {"instance_id": "a__a-1", "submission": "s2", "label": "unresolved"},
             {"instance_id": "b__b-1", "submission": "s1", "label": "resolved"}]
    for iid, sub, res in (("a__a-1", "s1", True), ("a__a-1", "s2", True)):
        d = tmp_path / AO.RUN_ID / (AO.MODEL_PREFIX + sub) / iid
        d.mkdir(parents=True)
        (d / "report.json").write_text(json.dumps({iid: {"resolved": res}}))
    out = AO.collect(pairs, tmp_path)
    assert out["n"] == 3 and out["agree"] == 1 and out["missing"] == 1
    assert out["by_label"] == {"resolved": {"n": 2, "agree": 1}, "unresolved": {"n": 1, "agree": 0}}
