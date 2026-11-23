import sys
import requests
from requests.utils import to_native_string

def main():
    # The issue states that calling requests.put with binary data fails
    # because of to_native_string being called on the data.
    # Specifically: requests.put("http://httpbin.org/put", data=u"ööö".encode("utf-8"))
    
    # We need to check if the internal processing of binary data causes an error.
    # Since we cannot make network requests, we need to trigger the code path
    # that processes the body/data before sending it out.
    
    # The error likely occurs in the preparation of the request body.
    # Let's look at how Request objects are prepared.
    
    binary_data = u"ööö".encode("utf-8")
    
    try:
        # Create a request object and prepare it. This exercises the code path
        # where data is processed, including calls to to_native_string if applicable.
        req = requests.Request('PUT', 'http://example.com/', data=binary_data)
        prepared = req.prepare()
        
        # If the bug is present, an exception (likely UnicodeDecodeError or similar)
        # would have been raised during prepare() when to_native_string was called
        # on the binary data.
        
        # Verify that the body is still bytes and unchanged
        assert prepared.body == binary_data, f"Body mismatch: {prepared.body!r} != {binary_data!r}"
        
        # If we get here without exception, the fix is working.
        sys.exit(0)
        
    except Exception as e:
        # If any exception occurs during preparation, the bug is still present.
        print(f"Error during request preparation: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
