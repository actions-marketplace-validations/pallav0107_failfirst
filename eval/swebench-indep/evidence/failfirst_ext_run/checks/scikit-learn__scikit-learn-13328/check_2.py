import numpy as np
from sklearn.datasets import make_regression
from sklearn.linear_model import HuberRegressor

# Reproduce the issue steps
X, y, coef = make_regression(n_samples=200, n_features=2, noise=4.0, coef=True, random_state=0)
X_bool = X > 0

# This should work without raising TypeError if the bug is fixed
try:
    huber = HuberRegressor().fit(X_bool, y)
except TypeError as e:
    # If TypeError is raised, the bug is still present
    raise AssertionError("TypeError raised when fitting HuberRegressor with boolean X: " + str(e))

# Additional check: ensure the model actually fitted successfully
assert hasattr(huber, 'coef_'), "HuberRegressor did not fit properly (no coef_ attribute)"

print("Check passed: HuberRegressor accepts boolean X.")
