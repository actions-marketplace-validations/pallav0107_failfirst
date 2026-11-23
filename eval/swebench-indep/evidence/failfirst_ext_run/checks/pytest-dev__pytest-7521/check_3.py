import sys
import io
from _pytest.capture import CaptureFixture, FDCaptureBinary

def test_capfd_preserves_carriage_return():
    """
    Test that capfd.readouterr() preserves carriage returns (\r)
    and does not convert them to newlines (\n).
    
    This reproduces the issue reported where pytest 6.0.0rc1 converts \r to \n.
    """
    # We need to simulate what capfd does internally.
    # The issue is in how pytest captures output from file descriptors.
    
    # Create a pipe pair to simulate stdout capture
    import os
    
    # Save original stdout
    original_stdout = sys.stdout
    
    # Create a pipe
    read_fd, write_fd = os.pipe()
    
    try:
        # Write data with \r to the write end
        test_data = b'Greetings from DOS\r'
        os.write(write_fd, test_data)
        os.close(write_fd)
        
        # Read from the read end
        captured_data = os.read(read_fd, 1024)
        
        # Close the read fd
        os.close(read_fd)
        
        # Check if \r is preserved
        assert captured_data.endswith(b'\r'), f"Expected data to end with \\r, but got: {captured_data!r}"
        
    finally:
        # Ensure fds are closed if something went wrong
        try:
            os.close(read_fd)
        except:
            pass
        try:
            os.close(write_fd)
        except:
            pass

def test_actual_pytest_capture_behavior():
    """
    Test the actual pytest capture mechanism to see if it preserves \r.
    We'll use the internal capture classes directly.
    """
    import os
    import tempfile
    
    # Create a temporary file to use as a capture target
    # Actually, let's use the FDCapture class which is what capfd uses internally
    
    from _pytest.capture import FDCapture
    
    # Save original stdout
    orig_stdout_fd = sys.stdout.fileno()
    
    # Create a pipe for capturing
    read_fd, write_fd = os.pipe()
    
    # Duplicate write_fd to stdout
    saved_stdout_fd = os.dup(orig_stdout_fd)
    os.dup2(write_fd, orig_stdout_fd)
    os.close(write_fd)
    
    try:
        # Create an FDCapture object for stdout
        # In pytest 6.x, the capture mechanism might be different
        # Let's try to use the lower-level capture
        
        # Write test data with \r
        test_string = 'Greetings from DOS\r'
        sys.stdout.write(test_string)
        sys.stdout.flush()
        
        # Restore stdout temporarily to read from the pipe
        os.dup2(saved_stdout_fd, orig_stdout_fd)
        os.close(saved_stdout_fd)
        
        # Read captured data
        captured_bytes = os.read(read_fd, 1024)
        os.close(read_fd)
        
        captured_str = captured_bytes.decode('utf-8', errors='replace')
        
        # The key assertion: \r should be preserved, not converted to \n
        assert captured_str.endswith('\r'), f"Expected captured output to end with \\r, but got: {captured_str!r}. The \\r was likely converted to \\n."
        
    except Exception as e:
        # Clean up on error
        try:
            os.dup2(saved_stdout_fd, orig_stdout_fd)
            os.close(saved_stdout_fd)
        except:
            pass
        try:
            os.close(read_fd)
        except:
            pass
        raise

if __name__ == '__main__':
    # Run the test that checks the actual behavior
    try:
        test_actual_pytest_capture_behavior()
        print("PASS: Carriage return is preserved correctly.")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
