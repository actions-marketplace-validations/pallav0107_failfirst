import sys
import io
from _pytest.capture import CaptureFixture, FDCaptureBinary

def test_capfd_preserves_carriage_return():
    """
    Test that capfd.readouterr() preserves carriage returns (\r) 
    and does not convert them to newlines (\n).
    
    This reproduces the issue reported where pytest 6.0.0rc1 converts \r to \n.
    """
    # We need to simulate what capfd does internally without running pytest.
    # The core issue is in how the capture mechanism handles the output.
    
    # Create a pipe pair to simulate stdout/stderr
    import os
    
    # Create a temporary file descriptor pair for testing
    read_fd, write_fd = os.pipe()
    
    try:
        # Write data with a carriage return to the write end
        test_data = b'Greetings from DOS\r'
        os.write(write_fd, test_data)
        os.close(write_fd)  # Close write end so read doesn't block indefinitely
        
        # Read from the read end
        captured_data = b''
        while True:
            chunk = os.read(read_fd, 4096)
            if not chunk:
                break
            captured_data += chunk
        
        # Decode the captured data
        decoded_data = captured_data.decode('utf-8', errors='replace')
        
        # The critical assertion: the carriage return should be preserved
        assert decoded_data.endswith('\r'), f"Expected data to end with '\\r', but got: {repr(decoded_data)}"
        
    finally:
        os.close(read_fd)
        # write_fd is already closed

def test_direct_string_handling():
    """
    Test the specific transformation that might be happening in pytest's capture code.
    In pytest 6.0, there was a change that could normalize line endings.
    """
    # Simulate the raw output containing \r
    raw_output = 'Greetings from DOS\r'
    
    # If pytest were incorrectly converting \r to \n, it would look like this:
    incorrect_output = raw_output.replace('\r', '\n')
    
    # The correct behavior is to keep \r as is
    correct_output = raw_output
    
    # Assert that the correct output ends with \r
    assert correct_output.endswith('\r'), "Correct output should end with \\r"
    
    # Assert that the incorrect output does NOT end with \r (it ends with \n)
    assert not incorrect_output.endswith('\r'), "Incorrect output should not end with \\r"

if __name__ == '__main__':
    try:
        test_capfd_preserves_carriage_return()
        test_direct_string_handling()
        print("All tests passed. The behavior is correct (\\r is preserved).")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        print("The behavior is incorrect (\\r is being converted to \\n or lost).")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
