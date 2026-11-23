import sys
import os
import runpy

# Save the original sys.path to restore later if needed, though we mainly care about the effect of runpy
original_path = list(sys.path)

# Insert a unique marker at the beginning of sys.path
marker = "UNIQUE_MARKER_FOR_TEST_12345"
sys.path.insert(0, marker)

# Verify it's there
assert sys.path[0] == marker, f"Marker not inserted correctly. First item: {sys.path[0]}"

# Run pylint via runpy as described in the issue
# We pass a dummy file or just let it run with --help or similar to trigger initialization
# The issue occurs during import/initialization of pylint when run via runpy
try:
    # alter_sys=True is key here as per the report
    runpy.run_module('pylint', run_name="__main__", alter_sys=True)
except SystemExit:
    # Pylint often exits with SystemExit (e.g., after printing help or version)
    pass

# Check if the marker is still in sys.path
if marker in sys.path:
    # The bug is fixed: pylint did not remove our custom path entry
    print("SUCCESS: Marker found in sys.path. Bug appears fixed.")
    sys.exit(0)
else:
    # The bug is present: pylint removed our custom path entry
    print("FAILURE: Marker missing from sys.path. Bug is still present.")
    assert False, f"The marker '{marker}' was removed from sys.path by pylint."
