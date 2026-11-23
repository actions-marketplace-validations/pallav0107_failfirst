import sys
import os

# Save the original sys.path to restore later if needed, 
# but we specifically need to test the behavior of runpy running pylint.

def main():
    # The issue states that when running pylint via runpy, it removes the first item from sys.path.
    # The user expects a check to ensure that the first item is "", "." or os.getcwd() before removing.
    
    # We simulate the environment described:
    # 1. Insert a custom path at the beginning of sys.path.
    # 2. Run pylint via runpy.
    # 3. Check if that custom path is still present in sys.path after execution.
    
    # Note: runpy.run_module with alter_sys=True modifies sys.path.
    # Pylint's __init__.py has logic to remove the first entry if it looks like a script directory.
    
    custom_path = "MY_CUSTOM_PATH_THAT_SHOULD_NOT_BE_REMOVED"
    
    # Insert our marker at position 0
    sys.path.insert(0, custom_path)
    
    # Verify it's there
    assert sys.path[0] == custom_path, "Failed to insert custom path"
    
    # We need to run pylint programmatically. 
    # Using runpy as described in the issue.
    import runpy
    
    # We run pylint on a dummy target or just help to make it exit quickly without needing files.
    # However, pylint might try to parse arguments. Let's try to run it with --help or version 
    # to minimize side effects, but the bug happens during initialization.
    
    # To avoid actual linting of files and complex argument parsing which might fail or hang,
    # we can try to trigger the initialization code path.
    # The problematic code is in pylint/__init__.py around line 99 (in the reported version).
    # It executes when pylint is invoked as a module.
    
    # Let's capture sys.path before and after.
    # Since runpy alters sys in place, we need to check the state after run_module returns.
    
    try:
        # Run pylint with --version so it exits quickly.
        # We need to pass arguments. runpy doesn't easily allow passing sys.argv.
        # But alter_sys=True sets sys.argv to ['<module>'] by default? 
        # Actually, runpy.run_module sets sys.argv[0] to the module name.
        # Pylint reads sys.argv. If we don't provide args, it might complain about missing files.
        # Let's try to just import and trigger the main logic manually if possible, 
        # but the issue specifically mentions runpy.
        
        # Alternative: Mimic what runpy does regarding sys.path manipulation if we can't easily use runpy 
        # with arguments. But let's stick to the reproduction case.
        
        # To make pylint exit cleanly, we can point it to a non-existent file? No, it errors.
        # We can use --help.
        
        # Save current argv
        old_argv = sys.argv
        
        # Set up argv for pylint to just show version and exit
        sys.argv = ['pylint', '--version']
        
        try:
            runpy.run_module('pylint', run_name="__main__", alter_sys=True)
        except SystemExit:
            # Pylint exits with SystemExit after printing version. This is expected.
            pass
        finally:
            # Restore argv
            sys.argv = old_argv
            
    except Exception as e:
        # If runpy fails for some other reason, we might need to handle it.
        # But for this test, we care about sys.path.
        print(f"Exception during runpy: {e}")
        # Even if it crashes, if the bug exists, sys.path might already be modified.
        
    # Check if our custom path is still in sys.path
    # The bug is that pylint removes sys.path[0] unconditionally (or based on weak checks).
    # If the fix is applied, it should only remove "" or "." or cwd.
    # Our custom path is none of those.
    
    if custom_path not in sys.path:
        # The bug is present: our path was removed incorrectly.
        raise AssertionError(f"The custom path '{custom_path}' was removed from sys.path, indicating the bug is still present.")
    else:
        # The fix is working: our path remains.
        print("Check passed: Custom path preserved.")
        sys.exit(0)

if __name__ == "__main__":
    main()
