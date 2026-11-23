import os
import sys
import tempfile
import shutil
import subprocess

def main():
    # Create a temporary directory structure to simulate the issue
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        gen_dir = os.path.join(src_dir, "gen")
        os.makedirs(gen_dir)

        # Create a dummy Python file in src/gen/ that should be ignored
        test_file = os.path.join(gen_dir, "test_ignored.py")
        with open(test_file, "w") as f:
            f.write("# This file should be ignored\nx=1\n")

        # Create a valid Python file in src/ that should be checked
        valid_file = os.path.join(src_dir, "valid.py")
        with open(valid_file, "w") as f:
            f.write("# Valid file\nprint('hello')\n")

        # Create pyproject.toml with ignore-paths configuration
        config_file = os.path.join(tmpdir, "pyproject.toml")
        with open(config_file, "w") as f:
            f.write("""[tool.pylint.MASTER]
ignore-paths = [
  "^src/gen/.*$",
]
""")

        # Run pylint with --recursive=y on the src directory
        # We use the system's pylint which should be installed in the environment
        cmd = [
            sys.executable, "-m", "pylint",
            "--recursive=y",
            "--rcfile=" + config_file,
            src_dir
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=tmpdir
        )

        stdout = result.stdout
        stderr = result.stderr
        
        # Combine output for checking
        full_output = stdout + stderr

        # Check if the ignored file was reported
        # If the bug exists, 'test_ignored.py' will appear in the output
        # If the bug is fixed, it should NOT appear in the output
        
        if "test_ignored.py" in full_output:
            print("FAIL: ignore-paths was ignored during recursive run. test_ignored.py was checked.")
            print("Output:", full_output)
            sys.exit(1)
        else:
            print("PASS: ignore-paths was respected. test_ignored.py was not checked.")
            sys.exit(0)

if __name__ == "__main__":
    main()
