import sys

def main():
    try:
        from astropy.io.fits import Header
    except ImportError:
        # If we can't import, we can't check, but usually this means env issue.
        # We'll assume the environment is set up correctly as per instructions.
        sys.exit(1)

    # A valid FITS header string (80 chars per line, ending with END + padding)
    # This is a minimal valid header.
    header_str = "SIMPLE  =                    T / conforms to FITS standard                      \n" \
                 "BITPIX  =                    8 / array data type                                \n" \
                 "NAXIS   =                    0 / number of array dimensions                     \n" \
                 "END                                                                                                                                                                                                                                 "

    # Pad the last line to 80 characters if necessary (it should be already)
    # The above string ends with END followed by spaces to make 80 chars.
    
    # Test 1: fromstring with unicode str (should work in both broken and fixed versions)
    try:
        h1 = Header.fromstring(header_str)
    except Exception as e:
        # If it fails on unicode str, something else is wrong
        print(f"Failed to parse unicode string: {e}")
        sys.exit(1)

    # Test 2: fromstring with bytes (the core of the issue)
    # In Python 3, bytes are not str. The issue states that fromstring does not accept bytes.
    header_bytes = header_str.encode('ascii')
    
    try:
        h2 = Header.fromstring(header_bytes)
    except TypeError as e:
        # If we get a TypeError, it likely means bytes are not accepted
        print(f"Header.fromstring failed with bytes: {e}")
        sys.exit(1)
    except Exception as e:
        # Other exceptions might indicate parsing errors, but let's see if it got past the type check
        print(f"Header.fromstring failed with bytes with unexpected error: {e}")
        sys.exit(1)

    # Verify that the parsed header from bytes is correct
    if 'SIMPLE' not in h2:
        print("Parsed header from bytes is missing SIMPLE keyword")
        sys.exit(1)
        
    if h2['SIMPLE'] != True:
        print("Parsed header from bytes has incorrect SIMPLE value")
        sys.exit(1)

    # Also check Card.fromstring as mentioned in the issue
    from astropy.io.fits.card import Card
    
    card_str = "SIMPLE  =                    T / conforms to FITS standard                      "
    card_bytes = card_str.encode('ascii')
    
    try:
        c1 = Card.fromstring(card_bytes)
    except TypeError as e:
        print(f"Card.fromstring failed with bytes: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Card.fromstring failed with bytes with unexpected error: {e}")
        sys.exit(1)
        
    if c1.keyword != 'SIMPLE':
        print("Parsed card from bytes has incorrect keyword")
        sys.exit(1)

    print("All checks passed. The issue appears to be fixed.")
    sys.exit(0)

if __name__ == '__main__':
    main()
