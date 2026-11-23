import tempfile
import os
import sys

def main():
    # Create a temporary directory for our test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple Python file with some code
        test_file = os.path.join(tmpdir, "test_module.py")
        with open(test_file, "w") as f:
            f.write("""
def foo():
    x = 1
    y = 2
    return x + y

def bar():
    a = 1
    b = 2
    return a + b
""")

        # Create a rcfile with min-similarity-lines set to 0
        rcfile = os.path.join(tmpdir, "pylint.rc")
        with open(rcfile, "w") as f:
            f.write("""[SIMILARITIES]
min-similarity-lines=0
""")

        # Run pylint programmatically
        from pylint.lint import PyLinter
        
        linter = PyLinter()
        linter.load_default_plugins()
        
        # Load the configuration
        linter.read_config_file(rcfile)
        linter.load_config_file()
        
        # Check the value of min_similarity_lines
        # In pylint 2.10, the option is stored in the similarities checker
        # We need to find the similarities checker and check its config
        
        # Get the similarities checker
        similarities_checker = None
        for checker in linter.get_checkers():
            if checker.name == 'similarities':
                similarities_checker = checker
                break
        
        assert similarities_checker is not None, "Similarities checker not found"
        
        # The issue states that setting min-similarity-lines to 0 should disable the check.
        # If the bug is present, it will treat every line as duplicate.
        # If the bug is fixed, it should disable the check entirely.
        
        # Let's check the actual behavior by running the linter on the test file
        # and seeing if any similarity messages are generated.
        
        # Clear any previous messages
        linter.msgs_store = None
        linter._msg_state = {}
        linter.msgs_store = linter.msgs_store or __import__('pylint.message').message.MessagesHandlerStore()
        
        # Re-initialize linter properly for checking
        from pylint import lint
        from pylint.reporters.text import TextReporter
        from io import StringIO
        
        output = StringIO()
        reporter = TextReporter(output)
        
        # Use Run class which handles initialization better
        from pylint.lint import Run
        
        # We need to capture if R0801 (duplicate code) is reported
        # Let's use a custom approach: run pylint with the specific config
        
        args = [
            test_file,
            f"--rcfile={rcfile}",
            "--disable=all",
            "--enable=duplicate-code",
            "--output-format=text"
        ]
        
        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = output
        sys.stderr = output
        
        try:
            # Run pylint
            run = Run(args, exit=False)
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        result = output.getvalue()
        
        # If min-similarity-lines=0 disables the check, there should be no R0801 messages
        # If the bug is present, there will be many R0801 messages
        
        has_duplicate_code_error = "R0801" in result or "duplicate-code" in result.lower()
        
        # The desired behavior (bug fixed): setting to 0 disables the check, so no errors
        # The buggy behavior: setting to 0 causes many errors
        
        # Assert that the behavior is correct (i.e., the bug is fixed)
        # If the bug is fixed, has_duplicate_code_error should be False
        assert not has_duplicate_code_error, f"Bug still present: duplicate code check was not disabled when min-similarity-lines=0. Output: {result}"

if __name__ == "__main__":
    main()
