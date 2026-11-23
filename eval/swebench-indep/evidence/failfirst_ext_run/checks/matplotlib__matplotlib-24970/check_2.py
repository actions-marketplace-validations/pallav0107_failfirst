import warnings
import sys

# Ensure we catch the specific NumPy deprecation warning as an error
warnings.filterwarnings('error', category=DeprecationWarning, message=".*NumPy will stop allowing conversion of out-of-bound Python integers.*")

import matplotlib.pyplot as plt
import numpy as np

try:
    # This is the exact reproduction code from the issue
    plt.get_cmap()(np.empty((0, ), dtype=np.uint8))
except DeprecationWarning:
    # If the warning is raised, it means the bug is still present
    print("FAIL: Deprecation warning was raised.")
    sys.exit(1)
except Exception as e:
    # If any other exception occurs, something else is wrong
    print(f"FAIL: Unexpected exception: {e}")
    sys.exit(1)

# If we reach here, no warning was raised, so the issue is fixed
print("PASS: No deprecation warning raised.")
sys.exit(0)
