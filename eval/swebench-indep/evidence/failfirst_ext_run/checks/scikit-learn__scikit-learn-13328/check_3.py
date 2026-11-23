import numpy as np
from sklearn.datasets import make_regression
from sklearn.linear_model import HuberRegressor

# Reproduce the issue exactly as described
X, y, coef = make_regression(n_samples=200, n_features=2, noise=4.0, coef=True, random_state=0)
X_bool = X > 0

# This should not raise a TypeError if the bug is fixed
try:
    huber = HuberRegressor().fit(X_bool, y)
except TypeError as e:
    # If we get a TypeError, the bug is still present
    raise AssertionError(f"HuberRegressor.fit failed with boolean X: {e}")

# Additional check: ensure the model actually fitted successfully
assert hasattr(huber, 'coef_'), "Model did not fit properly (no coef_ attribute)"
assert huber.coef_.shape == (2,), f"Unexpected coefficient shape: {huber.coef_.shape}"

print("Check passed: HuberRegressor accepts boolean X without TypeError.")
