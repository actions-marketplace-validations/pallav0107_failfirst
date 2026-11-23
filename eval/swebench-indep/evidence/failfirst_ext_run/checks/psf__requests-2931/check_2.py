import sys

def main():
    # The issue reports that requests.put with binary payload fails in 2.9
    # due to calling to_native_string on bytes.
    # We need to verify if this specific call raises an exception or not.
    
    import requests
    
    # We cannot make a real network request, but we can trigger the code path
    # that causes the error by preparing a request. The error occurs during
    # request preparation when headers/body are processed.
    
    try:
        # Create a session to use its prepare_request method which triggers
        # the internal processing where to_native_string is called on body/headers
        s = requests.Session()
        
        # Prepare a request with binary data as described in the issue
        req = requests.Request('PUT', 'http://example.com/', data=u"ööö".encode("utf-8"))
        prepared = s.prepare_request(req)
        
        # If we get here without exception, the bug is fixed.
        # The issue was that to_native_string was called on bytes, causing an error.
        # In fixed versions, bytes should be handled correctly.
        
        # Let's also verify the body is preserved correctly
        assert prepared.body == u"ööö".encode("utf-8"), "Body was modified incorrectly"
        
        print("Bug is fixed: binary payload handled correctly")
        sys.exit(0)
        
    except (TypeError, UnicodeDecodeError, AttributeError) as e:
        # These are the types of errors expected if to_native_string fails on bytes
        print(f"Bug still present: {type(e).__name__}: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected error
        print(f"Unexpected error: {type(e).__name__}: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
