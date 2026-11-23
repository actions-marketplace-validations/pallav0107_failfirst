import sys

def main():
    from astropy.io.fits import Header
    
    # Create a simple valid FITS header string
    header_str = "SIMPLE  =                    T / conforms to FITS standard                      \nBITPIX  =                    8 / array data type                                \nNAXIS   =                    0 / number of array dimensions                     \nEND                                                                             \n"
    
    # Test 1: Ensure it works with unicode str (this should work in both broken and fixed versions)
    try:
        h1 = Header.fromstring(header_str)
    except Exception as e:
        print(f"Failed to parse unicode string: {e}")
        sys.exit(1)
        
    # Test 2: Ensure it works with bytes (this is the bug report)
    header_bytes = header_str.encode('ascii')
    
    try:
        h2 = Header.fromstring(header_bytes)
    except TypeError as e:
        # If it raises TypeError, the bug is present
        print(f"Bug present: Header.fromstring does not accept bytes: {e}")
        sys.exit(1)
    except Exception as e:
        # Any other exception is also a failure
        print(f"Unexpected error when passing bytes: {e}")
        sys.exit(1)
        
    # Verify the resulting header is correct
    assert h2['SIMPLE'] == True
    assert h2['BITPIX'] == 8
    assert h2['NAXIS'] == 0
    
    print("Success: Header.fromstring accepts bytes.")
    sys.exit(0)

if __name__ == '__main__':
    main()
