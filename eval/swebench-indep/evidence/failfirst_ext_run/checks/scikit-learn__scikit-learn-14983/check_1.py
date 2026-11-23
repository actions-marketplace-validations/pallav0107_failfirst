from sklearn.model_selection import RepeatedKFold, RepeatedStratifiedKFold

# Test RepeatedKFold repr
rkf = RepeatedKFold()
rkf_repr = repr(rkf)
expected_rkf_repr = "RepeatedKFold(n_splits=5, n_repeats=10, random_state=None)"
assert rkf_repr == expected_rkf_repr, f"Expected '{expected_rkf_repr}', got '{rkf_repr}'"

# Test RepeatedStratifiedKFold repr
rskf = RepeatedStratifiedKFold()
rskf_repr = repr(rskf)
expected_rskf_repr = "RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=None)"
assert rskf_repr == expected_rskf_repr, f"Expected '{expected_rskf_repr}', got '{rskf_repr}'"

print("All checks passed.")
