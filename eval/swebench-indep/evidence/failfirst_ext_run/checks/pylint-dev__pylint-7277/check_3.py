import sys
import os

# We need to simulate the environment where a user has inserted a custom path
# at index 0, and then runs pylint via runpy. The bug is that pylint removes
# the first item of sys.path unconditionally, which breaks this use case.

# To check if the fix is present, we look at the source code of pylint.__init__
# or actually execute the logic in a controlled way. However, the most robust
# way to "exercise the behaviour" as requested is to actually trigger the code path.

# The issue states that when running from runpy, the first item is removed.
# Let's look at the specific line mentioned: pylint/__init__.py line 99 (in the old version).
# In newer versions, this logic might have moved or changed.

# The fix suggested is: Check if the first item is "", "." or os.getcwd() before removing.

# Let's try to import pylint and see if we can trigger the path manipulation.
# Actually, the manipulation happens during the import/initialization of pylint 
# when it's run as __main__. 

# We will use runpy to run pylint as a module, but we need to prevent it from 
# actually linting files (which might fail or take long). We can pass --help or 
# a non-existent file with --disable=all to make it exit quickly.

# However, simply importing pylint might not trigger the sys.path modification 
# if it's guarded by if __name__ == "__main__". The issue specifically mentions 
# runpy.run_module with alter_sys=True.

# Let's reproduce the exact scenario from the bug report.

def main():
    # Save original sys.path
    original_path = sys.path.copy()
    
    # Insert a dummy path at the beginning
    dummy_path = "MY_CUSTOM_DUMMY_PATH_12345"
    sys.path.insert(0, dummy_path)
    
    # Verify it's there
    assert sys.path[0] == dummy_path, "Failed to insert dummy path"
    
    # Now run pylint via runpy
    import runpy
    
    # We run pylint with --help so it exits quickly without doing real work
    # We need to capture the exit code or just let it run.
    # Note: runpy.run_module executes the module's code.
    
    # To avoid actual linting output cluttering, we can redirect stdout/stderr if needed,
    # but for this check, we care about sys.path side effects.
    
    # The bug causes sys.path[0] to be removed.
    # If fixed, sys.path[0] should remain because "MY_CUSTOM_DUMMY_PATH_12345" is not "" or "." or cwd.
    
    try:
        # Run pylint in a way that triggers the initialization code
        # Using --help ensures it exits cleanly and quickly
        runpy.run_module('pylint', run_name="__main__", alter_sys=True)
    except SystemExit:
        # Pylint exits with SystemExit after printing help
        pass
    
    # Check if our dummy path is still at index 0
    # If the bug is present, it was removed.
    # If the bug is fixed, it should still be there.
    
    if sys.path[0] == dummy_path:
        # The path was preserved. The fix is working.
        print("SUCCESS: sys.path[0] was preserved.")
        sys.exit(0)
    else:
        # The path was removed or changed. The bug is still present.
        print(f"FAILURE: sys.path[0] is now '{sys.path[0]}', expected '{dummy_path}'")
        assert False, f"The first item of sys.path was incorrectly removed. Expected '{dummy_path}', got '{sys.path[0]}'"

if __name__ == "__main__":
    main()
