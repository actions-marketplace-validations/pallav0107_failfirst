import numpy as np
from sklearn.linear_model import LogisticRegressionCV

# Reproduce the issue exactly as reported
np.random.seed(29)
X = np.random.normal(size=(1000, 3))
beta = np.random.normal(size=3)
intercept = np.random.normal(size=None)
y = np.sign(intercept + X @ beta)

try:
    clf = LogisticRegressionCV(
        cv=5,
        solver='saga',
        tol=1e-2,
        refit=False
    )
    clf.fit(X, y)
    # If we reach here, the bug is fixed (no IndexError thrown)
    print("Success: No IndexError thrown with refit=False")
except IndexError as e:
    # If IndexError is thrown, the bug is still present
    raise AssertionError(f"IndexError was thrown: {e}") from e
except Exception as e:
    # Any other unexpected exception
    raise AssertionError(f"Unexpected exception: {type(e).__name__}: {e}") from e
