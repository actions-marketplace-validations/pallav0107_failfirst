import sys

def main():
    from astropy.io.fits import Header
    
    # Create a simple valid FITS header string in ASCII
    header_str = "SIMPLE  =                    T / conforms to FITS standard                      \nBITPIX  =                   8 / array data type                                \nNAXIS   =                    0 / number of array dimensions                     \nEND                                                                             "
    
    # Test 1: Verify it works with unicode str (this should work in both broken and fixed versions)
    try:
        h1 = Header.fromstring(header_str)
    except Exception as e:
        print(f"Failed to parse unicode str: {e}")
        sys.exit(1)
        
    # Test 2: Verify it works with bytes (this is the bug reported)
    header_bytes = header_str.encode('ascii')
    
    try:
        h2 = Header.fromstring(header_bytes)
    except TypeError as e:
        # If it raises TypeError, the bug is still present
        print(f"Bug still present: Header.fromstring does not accept bytes. Error: {e}")
        sys.exit(1)
    except Exception as e:
        # If it raises another exception, something else is wrong
        print(f"Unexpected error when passing bytes: {e}")
        sys.exit(1)
        
    # Verify the parsed headers are equivalent
    assert dict(h1) == dict(h2), "Headers parsed from str and bytes are not equivalent"
    
    # Test Card.fromstring as mentioned in the issue
    from astropy.io.fits.card import Card
    
    card_str = "SIMPLE  =                    T / conforms to FITS standard                      "
    card_bytes = card_str.encode('ascii')
    
    try:
        c1 = Card.fromstring(card_str)
    except Exception as e:
        print(f"Failed to parse Card from unicode str: {e}")
        sys.exit(1)
        
    try:
        c2 = Card.fromstring(card_bytes)
    except TypeError as e:
        print(f"Bug still present: Card.fromstring does not accept bytes. Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error when passing bytes to Card.fromstring: {e}")
        sys.exit(1)
        
    assert str(c1) == str(c2), "Cards parsed from str and bytes are not equivalent"

    print("All checks passed. The issue is fixed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
