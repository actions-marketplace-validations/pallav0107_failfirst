import sys

def check_builtin_str_behavior():
    """
    Check if builtin_str correctly handles binary strings.
    
    The issue reports that builtin_str(b'GET') returns "b'GET'" (the literal string representation)
    instead of "GET" (the decoded string). This causes HTTP requests to fail with 404 because
    the method name is incorrect.
    """
    try:
        from requests.compat import builtin_str
    except ImportError:
        # Try alternative import paths for different versions
        try:
            from requests.utils import builtin_str
        except ImportError:
            # If we can't find builtin_str, we need to check the actual behavior
            # by looking at how requests handles binary method names
            print("Could not import builtin_str directly, testing behavior indirectly")
            return test_method_handling_indirectly()
    
    # Test the specific case mentioned in the issue
    binary_method = b'GET'
    result = builtin_str(binary_method)
    
    # The correct behavior should be that builtin_str(b'GET') returns 'GET'
    # The buggy behavior returns "b'GET'" (the string representation of the bytes object)
    
    expected = 'GET'
    if result == expected:
        print(f"PASS: builtin_str(b'GET') correctly returned '{result}'")
        return True
    else:
        print(f"FAIL: builtin_str(b'GET') returned '{result}' instead of '{expected}'")
        return False

def test_method_handling_indirectly():
    """
    Test how requests handles binary method names by checking the prepared request.
    """
    try:
        import requests
        from requests import Request
        
        # Create a request with a binary method
        req = Request(method=b'GET', url='http://example.com')
        prepared = req.prepare()
        
        # Check what the method actually is in the prepared request
        method = prepared.method
        
        # The method should be 'GET', not "b'GET'"
        if method == 'GET':
            print(f"PASS: Prepared request method is correctly '{method}'")
            return True
        else:
            print(f"FAIL: Prepared request method is '{method}' instead of 'GET'")
            return False
    except Exception as e:
        print(f"Error during indirect test: {e}")
        return False

def main():
    try:
        is_correct = check_builtin_str_behavior()
        if is_correct:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
