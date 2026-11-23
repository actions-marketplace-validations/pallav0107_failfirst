from sklearn.model_selection import RepeatedKFold, RepeatedStratifiedKFold

# Check RepeatedKFold repr
rkf = RepeatedKFold()
repr_rkf = repr(rkf)
expected_rkf = "RepeatedKFold(n_splits=5, n_repeats=10, random_state=None)"
assert repr_rkf == expected_rkf, f"Expected '{expected_rkf}', but got '{repr_rkf}'"

# Check RepeatedStratifiedKFold repr
rskf = RepeatedStratifiedKFold()
repr_rskf = repr(rskf)
expected_rskf = "RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=None)"
assert repr_rskf == expected_rskf, f"Expected '{expected_rskf}', but got '{repr_rskf}'"

print("All checks passed.")
