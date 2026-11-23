import sys
import tempfile
import os

def main():
    # Create a temporary directory for our test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two identical Python files to trigger duplicate code detection
        file1_path = os.path.join(tmpdir, "file1.py")
        file2_path = os.path.join(tmpdir, "file2.py")
        
        content = """
def hello():
    print("Hello World")
    x = 1
    y = 2
    z = x + y
    return z
"""
        with open(file1_path, "w") as f:
            f.write(content)
        with open(file2_path, "w") as f:
            f.write(content)

        # Create a rcfile with min-similarity-lines set to 0
        rcfile_path = os.path.join(tmpdir, "pylint.rc")
        with open(rcfile_path, "w") as f:
            f.write("[SIMILARITIES]\n")
            f.write("min-similarity-lines=0\n")

        # Import pylint here to ensure environment is ready
        from pylint.lint import PyLinter
        from pylint.config import find_default_config_files

        # We need to run pylint programmatically to check the behavior
        # We will use the Run class or similar to capture output/errors
        
        # Let's use the standard pylint run interface but capture the exit code and messages
        from pylint import lint
        
        # Arguments: the two files, using our custom rcfile
        args = [
            file1_path,
            file2_path,
            f"--rcfile={rcfile_path}",
            "--disable=all",
            "--enable=duplicate-code", # Ensure only duplicate code is checked
            "--output-format=text"
        ]
        
        # We need to check if setting min-similarity-lines to 0 disables the check.
        # The issue states that currently it treats every line as duplicate (bad).
        # The desired behavior is that it disables the check (no errors).
        
        # Let's run pylint
        try:
            # Use linter directly to have more control
            linter = PyLinter()
            linter.load_default_plugins()
            
            # Parse arguments including rcfile
            # Note: Pylint's argument parsing can be complex. 
            # A simpler way is to use pylint.testutils or just subprocess, 
            # but we are asked not to rely on test suite.
            # However, importing and running via lint.Run is standard usage.
            
            # To avoid sys.exit from Run, we catch it or use Linter directly.
            # Let's try using the Linter API directly.
            
            # Reset linter
            linter = PyLinter()
            linter.load_default_plugins()
            
            # Set options manually to avoid rcfile parsing issues if any
            # But the issue is specifically about rcfile setting.
            # So we should probably let it parse the rcfile.
            
            # Let's use lint.Run which handles config loading properly
            # We need to prevent sys.exit
            from io import StringIO
            
            old_stderr = sys.stderr
            old_stdout = sys.stdout
            sys.stderr = StringIO()
            sys.stdout = StringIO()
            
            exit_code = None
            try:
                run = lint.Run(args, exit=False)
                exit_code = run.linter.msg_status
            except SystemExit as e:
                exit_code = e.code
            finally:
                sys.stderr = old_stderr
                sys.stdout = old_stdout
                
            # If min-similarity-lines=0 disables the check, there should be no duplicate-code messages.
            # The exit code should be 0 (no errors).
            # If it's broken, it will report duplicates and exit code != 0.
            
            # According to the issue:
            # Current (broken): raises many errors.
            # Desired (fixed): disables check (no errors).
            
            # So if fixed, exit_code should be 0.
            
            # However, we must be careful. Does 0 mean "disabled" or "match everything"?
            # The issue says "Setting min-similarity-lines to 0 should disable the duplicate code check."
            
            # Let's assert that the exit code is 0, meaning no issues found.
            assert exit_code == 0, f"Expected exit code 0 (check disabled), but got {exit_code}. The bug is likely still present."
            
        except Exception as e:
            # If something goes wrong in setup, fail
            raise AssertionError(f"Failed to run pylint: {e}")

if __name__ == "__main__":
    main()
