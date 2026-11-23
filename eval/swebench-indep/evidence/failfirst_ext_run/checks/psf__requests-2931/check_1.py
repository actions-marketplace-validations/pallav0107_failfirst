import sys
import requests
from requests.structures import CaseInsensitiveDict
from requests.utils import to_native_string

def test_binary_payload_with_to_native_string():
    """
    Test that binary data can be prepared for a request without raising an error
    in to_native_string.
    
    The issue is that in version 2.9, calling requests.put with binary data
    (bytes) fails because somewhere in the preparation chain, to_native_string
    is called on the binary data, which expects a string.
    
    We simulate what happens during request preparation by checking if
    to_native_string handles bytes correctly or if it raises an error.
    
    However, since we cannot make actual network calls, we need to test the
    internal behavior that causes the failure. The fix should ensure that
    binary data is not passed to to_native_string, or that to_native_string
    handles bytes gracefully.
    """
    
    # The core issue: to_native_string should not be called on binary data
    # Let's check if passing bytes to to_native_string causes an issue
    binary_data = u"ööö".encode("utf-8")
    
    # In the fixed version, the code path should avoid calling to_native_string
    # on binary data. We'll test by preparing a request and seeing if it fails.
    
    try:
        # Create a PreparedRequest to trigger the same code path as requests.put
        s = requests.Session()
        req = requests.Request('PUT', "http://example.com/put", data=binary_data)
        prepared = s.prepare_request(req)
        
        # If we get here without exception, the basic preparation works
        # Now let's verify the body is still bytes
        assert isinstance(prepared.body, bytes), f"Expected body to be bytes, got {type(prepared.body)}"
        assert prepared.body == binary_data, f"Body mismatch: expected {binary_data!r}, got {prepared.body!r}"
        
    except (UnicodeDecodeError, AttributeError, TypeError) as e:
        # These are the kinds of errors that would occur if to_native_string
        # is incorrectly called on binary data
        raise AssertionError(f"Request preparation failed with binary data: {e}") from e
    
    print("Test passed: Binary payload handling works correctly.")

if __name__ == "__main__":
    test_binary_payload_with_to_native_string()
    sys.exit(0)
