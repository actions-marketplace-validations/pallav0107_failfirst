import numpy as np
from sklearn.linear_model import LogisticRegressionCV

# Reproduce the exact scenario from the issue report
np.random.seed(29)
X = np.random.normal(size=(1000, 3))
beta = np.random.normal(size=3)
intercept = np.random.normal(size=None)
y = np.sign(intercept + X @ beta)

try:
    # This should raise an IndexError in the buggy version (0.21.2/0.22)
    # and succeed in the fixed version.
    lr_cv = LogisticRegressionCV(
        cv=5,
        solver='saga',
        tol=1e-2,
        refit=False
    )
    lr_cv.fit(X, y)
    
    # If we reach here, the bug is fixed.
    # We assert that no exception was raised.
    assert True
    
except IndexError as e:
    # If IndexError is raised, the bug is still present.
    # We raise an AssertionError to signal failure (non-zero exit code).
    raise AssertionError(f"IndexError was raised, indicating the bug is still present: {e}")
except Exception as e:
    # Any other unexpected exception should also fail the check
    raise AssertionError(f"Unexpected exception raised: {type(e).__name__}: {e}")
