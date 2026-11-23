import subprocess
import sys
import tempfile
import os

def main():
    # Create a temporary Python file to lint
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('print("hello")\n')
        temp_file = f.name

    try:
        # Test the short option -v which should NOT require an argument
        # If the bug exists, this will fail with "expected one argument"
        result = subprocess.run(
            [sys.executable, '-m', 'pylint', temp_file, '-v'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if the command failed due to the specific bug
        # The bug causes pylint to exit with error code 2 and print 
        # "argument --verbose/-v: expected one argument"
        if result.returncode != 0:
            stderr = result.stderr.lower()
            stdout = result.stdout.lower()
            combined_output = stderr + stdout
            
            # If the error message mentions expecting an argument for verbose/-v, the bug is present
            if 'expected one argument' in combined_output and ('-v' in combined_output or '--verbose' in combined_output):
                print("Bug is present: -v option incorrectly expects an argument")
                assert False, "The short verbose option (-v) should not expect an argument"
        
        # If we get here, the command didn't fail with the specific bug error
        # The issue is fixed if -v works without requiring an argument
        print("Bug appears to be fixed: -v option works without requiring an argument")
        assert True
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file):
            os.unlink(temp_file)

if __name__ == '__main__':
    main()
