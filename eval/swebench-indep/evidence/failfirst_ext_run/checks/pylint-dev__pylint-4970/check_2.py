import sys
import tempfile
import os

def main():
    # Create a temporary directory for our test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two identical Python files to trigger similarity check
        file1_path = os.path.join(tmpdir, "file1.py")
        file2_path = os.path.join(tmpdir, "file2.py")
        
        content = """
def hello():
    print("hello world")
    x = 1
    y = 2
    z = 3
    return x + y + z
"""
        with open(file1_path, "w") as f:
            f.write(content)
        with open(file2_path, "w") as f:
            f.write(content)

        # Create a rcfile with min-similarity-lines set to 0
        rcfile_path = os.path.join(tmpdir, "pylintrc")
        with open(rcfile_path, "w") as f:
            f.write("[SIMILARITIES]\n")
            f.write("min-similarity-lines=0\n")

        # Run pylint programmatically
        from pylint.lint import PyLinter
        from pylint.config import find_default_config_files
        
        linter = PyLinter()
        
        # Register standard checkers
        linter.load_default_plugins()
        
        # Read the config file
        linter.read_config_file(rcfile_path)
        linter.load_config_file()
        
        # Check the value of min-similarity-lines
        # In pylint 2.10, the option is stored in the similarities checker configuration
        # We need to access the checker specifically
        
        # Let's try running pylint on the files and capture the output
        import io
        from contextlib import redirect_stdout, redirect_stderr
        
        # Re-initialize linter properly
        linter = PyLinter()
        linter.load_default_plugins()
        
        # Set the option directly before parsing command line if possible, 
        # or use the rcfile approach via command line arguments simulation
        
        # Alternative: Use run_pylint style invocation
        from pylint import lint
        
        # Prepare arguments
        args = [
            file1_path,
            file2_path,
            f"--rcfile={rcfile_path}",
            "--disable=all",
            "--enable=duplicate-code",
        ]
        
        # Capture output
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                lint.Run(args, exit=False)
        except SystemExit:
            pass # lint.Run may call sys.exit, we ignore it
        
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        combined_output = stdout_val + stderr_val
        
        # If min-similarity-lines=0 disables the check, there should be NO duplicate code warnings
        # The issue states that currently it treats every line as duplicate (wrong behavior)
        # The desired behavior is that it disables the check entirely
        
        # Check if R0801 (duplicate-code) appears in the output
        has_duplicate_code_warning = "R0801" in combined_output or "duplicate-code" in combined_output
        
        # If the fix is correct, setting min-similarity-lines to 0 should disable the check
        # Therefore, there should be NO duplicate code warnings
        assert not has_duplicate_code_warning, (
            "Setting min-similarity-lines to 0 should disable duplicate code checking, "
            "but duplicate code warnings were found. Output:\n" + combined_output
        )
        
        sys.exit(0)

if __name__ == "__main__":
    main()
