import sys
import tempfile
import os

def main():
    # Create a temporary directory for the test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy Python file to lint
        dummy_file = os.path.join(tmpdir, "dummy.py")
        with open(dummy_file, "w") as f:
            f.write("foo = 1\n")

        # Create a pylintrc configuration file with a regex containing a comma
        config_file = os.path.join(tmpdir, "pylintrc")
        # The issue states that bad-name-rgxs splits on commas, mangling regexes like "(foo{1,3})"
        # We use the exact example from the bug report.
        config_content = """[tool.pylint.basic]
bad-name-rgxs = "(foo{1,3})"
"""
        with open(config_file, "w") as f:
            f.write(config_content)

        # Import pylint components
        try:
            from pylint.lint import Run
        except ImportError:
            # Fallback for older versions or different structures
            from pylint import lint
            Run = lint.Run

        # Attempt to run pylint with the problematic configuration
        # If the bug exists, this will raise an exception (re.error) during initialization
        # because the regex is split incorrectly.
        # If the bug is fixed, it should handle the regex correctly (either by not splitting
        # inside quotes or by using a different delimiter) and not crash.
        
        exit_code = 0
        try:
            # We pass the dummy file and the config file
            # Note: PylintRun usually takes argv-like arguments
            args = [dummy_file, f"--rcfile={config_file}"]
            
            # We need to capture if it crashes during init. 
            # Run(...) initializes and runs. If it crashes during init due to config parsing,
            # it will raise an exception before returning.
            runner = Run(args, exit=False)
            
            # If we get here, the initialization succeeded.
            # The behavior is correct (fixed).
            exit_code = 0
            
        except Exception as e:
            # If an exception occurred, specifically related to regex parsing or config loading
            # then the bug is still present.
            print(f"Exception caught: {type(e).__name__}: {e}")
            # Check if it's the specific error mentioned in the issue
            if "missing ), unterminated subpattern" in str(e) or "re.error" in str(type(e)):
                exit_code = 1
            else:
                # Some other unexpected error, but likely still a failure of the feature
                exit_code = 1

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
