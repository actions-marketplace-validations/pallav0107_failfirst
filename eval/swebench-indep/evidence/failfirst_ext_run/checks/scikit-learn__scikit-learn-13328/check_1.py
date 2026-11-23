import numpy as np
from sklearn.datasets import make_regression
from sklearn.linear_model import HuberRegressor

# Reproduce the issue steps
X, y, coef = make_regression(n_samples=200, n_features=2, noise=4.0, coef=True, random_state=0)
X_bool = X > 0

# The issue states that fitting with boolean X raises TypeError
# If fixed, this should run without error
try:
    huber = HuberRegressor().fit(X_bool, y)
except TypeError as e:
    # If TypeError is raised, the bug is still present
    raise AssertionError("TypeError was raised when fitting HuberRegressor with boolean X. Bug is not fixed.") from e

# Additional check: ensure the model actually fitted successfully
assert hasattr(huber, 'coef_'), "Model did not fit correctly (no coef_ attribute)"

print("Bug is fixed: HuberRegressor accepts boolean X without TypeError.")
