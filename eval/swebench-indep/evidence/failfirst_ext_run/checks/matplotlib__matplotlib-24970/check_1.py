import warnings
import sys

# Reproduce the exact code from the issue
import matplotlib.pyplot as plt
import numpy as np

# Capture warnings
with warnings.catch_warnings(record=True) as w:
    # Ensure all warnings are caught, including DeprecationWarnings
    warnings.simplefilter("always")
    
    # Execute the reproduction code
    plt.get_cmap()(np.empty((0, ), dtype=np.uint8))
    
    # Filter for NumPy deprecation warnings regarding out-of-bound integers
    numpy_deprecation_warnings = [
        warning for warning in w 
        if issubclass(warning.category, DeprecationWarning) 
        and "NumPy will stop allowing conversion of out-of-bound Python integers" in str(warning.message)
    ]

# If any such warnings were raised, the bug is present (exit non-zero)
# If no such warnings were raised, the bug is fixed (exit 0)
assert len(numpy_deprecation_warnings) == 0, f"Found {len(numpy_deprecation_warnings)} NumPy deprecation warnings: {[str(w.message) for w in numpy_deprecation_warnings]}"

sys.exit(0)
