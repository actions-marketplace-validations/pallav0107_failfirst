import numpy as np
from sklearn.linear_model import LogisticRegressionCV

# Reproduce the exact scenario from the issue report
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
    # If we reach here, the bug is fixed (no IndexError was thrown)
    print("Success: No IndexError thrown with refit=False")
except IndexError as e:
    # If IndexError is thrown, the bug is still present
    raise AssertionError(f"Bug is still present: IndexError thrown with refit=False. Error: {e}")
except Exception as e:
    # Any other unexpected error
    raise AssertionError(f"Unexpected error occurred: {type(e).__name__}: {e}")
