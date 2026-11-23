import warnings
import sys

# Reproduce the exact code from the issue
import matplotlib.pyplot as plt
import numpy as np

# Capture all warnings
with warnings.catch_warnings(record=True) as w:
    # Ensure all warnings are always caught
    warnings.simplefilter("always")
    
    # Execute the reproduction code
    plt.get_cmap()(np.empty((0, ), dtype=np.uint8))
    
    # Check if any DeprecationWarning related to NumPy integer conversion was raised
    numpy_deprecation_found = False
    for warning in w:
        if issubclass(warning.category, DeprecationWarning):
            if "NumPy will stop allowing conversion of out-of-bound Python integers" in str(warning.message):
                numpy_deprecation_found = True
                break

    # If such a warning is found, the bug is still present (incorrect behavior)
    # We want the script to exit 0 if fixed, non-zero if broken.
    # So we assert that NO such warning was found.
    assert not numpy_deprecation_found, "NumPy 1.24 deprecation warning regarding out-of-bound integer conversion was raised."

sys.exit(0)
