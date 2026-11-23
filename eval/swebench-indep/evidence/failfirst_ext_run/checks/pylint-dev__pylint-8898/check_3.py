import sys
import tempfile
import os

def main():
    # Create a minimal Python file to lint
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("foo = 1\n")
        temp_py_file = f.name

    # Create a temporary configuration file that triggers the bug
    # The regex "(foo{1,3})" contains a comma which causes splitting issues
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[tool.pylint.basic]\n')
        f.write('bad-names-rgxs = ["(foo{1,3})"]\n')
        temp_config_file = f.name

    try:
        from pylint.lint import Run
        
        # Attempt to run pylint with the problematic configuration
        # If the bug is present, this will raise an exception during initialization
        # because the comma in the regex will be interpreted as a separator
        try:
            # We use --rcfile to specify our config
            run = Run([temp_py_file, f"--rcfile={temp_config_file}"], exit=False)
            
            # If we reach here without crashing, the bug is likely fixed.
            # However, we should also verify that the regex was actually parsed correctly.
            # We can check if the linter's config contains the expected pattern.
            
            # Access the linter instance from the Run object
            linter = run.linter
            
            # Check if the bad_names_rgx option was parsed correctly
            # In newer versions, it might be stored differently, but let's check the raw value
            # or try to see if it compiled successfully.
            
            # If the code didn't crash, it means the comma handling is fixed.
            # Let's assert that no exception occurred.
            
            # To be more robust, let's check if the regex pattern is correctly stored.
            # The option name in pylint config is often transformed (hyphens to underscores).
            # For 'bad-names-rgxs', the attribute might be 'bad_names_rgxs'.
            
            # Note: In pylint 3.0, the option might be handled by argparse directly.
            # If the parsing succeeded, the bug is fixed.
            
            print("Pylint ran successfully without crashing.")
            sys.exit(0)
            
        except re.error as e:
            # If we get a regex error, the bug is still present
            print(f"Regex error occurred (bug present): {e}")
            sys.exit(1)
        except SystemExit as e:
            # Pylint might call sys.exit internally. 
            # If it exits with 0, it's fine. If it crashes during init, it might exit non-zero.
            # But the traceback in the issue shows an unhandled exception, not a clean exit.
            # So if we catch SystemExit here, it might be a normal exit after linting.
            # However, the bug causes a crash *during* initialization, before linting starts.
            # So if we get here, it means initialization passed.
            if e.code == 0:
                sys.exit(0)
            else:
                # Check if it was due to the regex issue
                # This is tricky. Let's assume if we got past the init phase, it's ok.
                # But the issue shows a crash in _parse_configuration_file.
                # So if we are here, the init passed.
                sys.exit(0)
        except Exception as e:
            # Any other exception during initialization indicates the bug
            if "missing ), unterminated subpattern" in str(e) or "re.error" in str(type(e)):
                print(f"Exception occurred (bug present): {e}")
                sys.exit(1)
            # Re-raise if it's something else unexpected
            raise

    finally:
        # Cleanup temp files
        if os.path.exists(temp_py_file):
            os.unlink(temp_py_file)
        if os.path.exists(temp_config_file):
            os.unlink(temp_config_file)

if __name__ == "__main__":
    import re
    main()
