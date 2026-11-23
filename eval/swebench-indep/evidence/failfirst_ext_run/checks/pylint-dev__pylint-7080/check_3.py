import os
import sys
import tempfile
import shutil
import subprocess

def main():
    # Create a temporary directory structure to reproduce the issue
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        gen_dir = os.path.join(src_dir, "gen")
        os.makedirs(gen_dir)

        # Create a dummy Python file in src/gen that would trigger errors if linted
        test_file = os.path.join(gen_dir, "test_module.py")
        with open(test_file, "w") as f:
            f.write("x=1\n") # Simple syntax, but we want to ensure it's ignored

        # Create a pyproject.toml with ignore-paths configuration
        config_file = os.path.join(tmpdir, "pyproject.toml")
        with open(config_file, "w") as f:
            f.write("""[tool.pylint.MASTER]
ignore-paths = [
  "^src/gen/.*$",
]
""")

        # Run pylint recursively on src/
        # We use the subprocess module to run pylint as a command line tool
        # because the issue is about CLI behavior.
        cmd = [
            sys.executable, "-m", "pylint",
            "--recursive=y",
            f"--rcfile={config_file}",
            "src/"
        ]
        
        # Execute from the tmpdir root so relative paths in config match
        result = subprocess.run(
            cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        # Check if any file from src/gen was linted.
        # If ignore-paths works, src/gen/test_module.py should NOT appear in the output.
        # If it fails, it will appear.
        
        # We look for the filename in the output. 
        # Pylint output format usually starts with ************* Module name or filepath:line...
        
        if "src/gen/test_module.py" in stdout or "src/gen/test_module.py" in stderr:
            print("FAIL: ignore-paths was ignored. File src/gen/test_module.py was linted.")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            sys.exit(1)
        
        # Also check if any other file in gen was linted (just in case)
        if "src/gen" in stdout or "src/gen" in stderr:
             # Be careful, this might match other things, but specifically looking for lint results
             # A more robust check is looking for specific error lines associated with files in gen
             pass

        # To be absolutely sure, let's verify that pylint actually ran and didn't just crash
        # If it crashed, it might not have linted anything, which is technically "ignoring" but not correctly.
        # However, the issue is specifically about ignore-paths being ignored.
        
        # Let's add a file outside gen to ensure pylint is working at all
        good_file = os.path.join(src_dir, "good_module.py")
        with open(good_file, "w") as f:
            f.write("# Good module\n")
            
        # Re-run to ensure we have some output to confirm pylint is active
        # Actually, we can just check the previous run. If pylint ran successfully, 
        # it should have found 'good_module.py' if it was traversing src/.
        
        # Wait, the previous run didn't include good_module.py in the setup? 
        # Let's refine the test.
        
        pass

    # Refined Test Logic
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        gen_dir = os.path.join(src_dir, "gen")
        os.makedirs(gen_dir)

        # File that SHOULD be ignored
        ignored_file = os.path.join(gen_dir, "ignored.py")
        with open(ignored_file, "w") as f:
            f.write("invalid syntax !!!\n")

        # File that SHOULD be checked
        checked_file = os.path.join(src_dir, "checked.py")
        with open(checked_file, "w") as f:
            f.write("valid_code = True\n")

        config_file = os.path.join(tmpdir, "pyproject.toml")
        with open(config_file, "w") as f:
            f.write("""[tool.pylint.MASTER]
ignore-paths = [
  "^src/gen/.*$",
]
""")

        cmd = [
            sys.executable, "-m", "pylint",
            "--recursive=y",
            f"--rcfile={config_file}",
            "src/"
        ]
        
        result = subprocess.run(
            cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        output = result.stdout + result.stderr
        
        # Assertion 1: The ignored file should NOT be in the output
        # If it is, it means ignore-paths failed.
        assert "ignored.py" not in output, f"ignore-paths failed: 'ignored.py' was linted.\nOutput:\n{output}"
        
        # Assertion 2: The checked file SHOULD be in the output (or at least pylint ran without crashing on it)
        # Since checked.py has no errors, it might not appear in error output, but pylint should exit cleanly
        # or report it as rated.
        # A better check: create a file with an error outside gen to ensure pylint is working.
        
        pass

    # Final Robust Test
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        gen_dir = os.path.join(src_dir, "gen")
        os.makedirs(gen_dir)

        # File that SHOULD be ignored (contains syntax error to make detection easy)
        ignored_file = os.path.join(gen_dir, "ignored.py")
        with open(ignored_file, "w") as f:
            f.write("!!! invalid syntax\n")

        # File that SHOULD be checked (contains a deliberate lint error)
        checked_file = os.path.join(src_dir, "checked.py")
        with open(checked_file, "w") as f:
            f.write("import os\nimport sys\n# unused imports\n")

        config_file = os.path.join(tmpdir, "pyproject.toml")
        with open(config_file, "w") as f:
            f.write("""[tool.pylint.MASTER]
ignore-paths = [
  "^src/gen/.*$",
]
""")

        cmd = [
            sys.executable, "-m", "pylint",
            "--recursive=y",
            f"--rcfile={config_file}",
            "src/"
        ]
        
        result = subprocess.run(
            cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        output = result.stdout + result.stderr
        
        # 1. Ensure the ignored file was NOT processed. 
        # If it were processed, pylint would likely report a syntax error or parse error.
        assert "ignored.py" not in output, f"FAILURE: ignore-paths is broken. 'ignored.py' was processed.\n{output}"
        
        # 2. Ensure the checked file WAS processed.
        # It has unused imports, so pylint should report them.
        assert "checked.py" in output, f"FAILURE: pylint did not process 'checked.py'.\n{output}"
        
        print("SUCCESS: ignore-paths works correctly with --recursive=y")
        sys.exit(0)

if __name__ == "__main__":
    main()
