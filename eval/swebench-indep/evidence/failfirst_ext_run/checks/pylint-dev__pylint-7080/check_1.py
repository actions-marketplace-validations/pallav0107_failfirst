import os
import sys
import tempfile
import shutil

def main():
    # Create a temporary directory structure to simulate the issue
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        gen_dir = os.path.join(src_dir, "gen")
        os.makedirs(gen_dir)

        # Create a dummy Python file in src/gen/ that would trigger errors if linted
        # Using a simple syntax error or style violation is enough, but let's use something
        # that pylint definitely catches, like an undefined variable.
        test_file = os.path.join(gen_dir, "test_module.py")
        with open(test_file, "w") as f:
            f.write("undefined_variable = 1\n")

        # Create pyproject.toml with ignore-paths configuration
        config_file = os.path.join(tmpdir, "pyproject.toml")
        with open(config_file, "w") as f:
            f.write("""
[tool.pylint.MASTER]
ignore-paths = [
  "^src/gen/.*$",
]
""")

        # We need to run pylint from the tmpdir so it picks up pyproject.toml
        # and uses src/ as the target.
        
        # Import pylint components
        from pylint.lint import PyLinter
        from pylint.config import find_default_config_files
        
        # Change working directory to tmpdir to ensure config is found
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Initialize linter
            linter = PyLinter()
            
            # Register standard checkers
            linter.load_default_plugins()
            
            # Read configuration from pyproject.toml
            # In pylint 2.15, we can use the argument parser or config manager
            # Let's try to mimic the command line: pylint --recursive=y src/
            
            # We need to manually set up the options as if they were passed via CLI
            # or loaded from config.
            
            # Load config file explicitly to be sure
            linter.read_config_file(config_file)
            linter.load_config_file()
            
            # Set recursive option
            linter.set_option('recursive', True)
            
            # Check if ignore-paths was loaded correctly
            ignore_paths = linter.config.ignore_paths
            if not ignore_paths:
                print("ERROR: ignore-paths not loaded from config")
                return 1
                
            # Prepare arguments for checking
            args = [os.path.join(tmpdir, "src")]
            
            # Run check
            # We capture the messages to see if files in gen/ were checked
            linter.check(args)
            
            # Get all messages
            messages = linter.reporter.messages if hasattr(linter.reporter, 'messages') else []
            
            # In newer pylint versions, reporter might be different. 
            # Let's look at the message store.
            # Actually, PyLinter.check doesn't return messages directly in older versions easily.
            # Let's use the internal state.
            
            # A more robust way: check if any message comes from a file in src/gen/
            found_gen_error = False
            for msg in linter.reporter.messages:
                if "src" in msg.path and "gen" in msg.path:
                    found_gen_error = True
                    break
            
            # If ignore-paths works, no messages should come from src/gen/
            if found_gen_error:
                print("FAIL: Files in ignored path were checked")
                return 1
            else:
                print("PASS: Ignored paths were correctly skipped")
                return 0

        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    sys.exit(main())
