import sys
import tempfile
import os

def main():
    # Create a temporary MRT file content as described in the issue
    mrt_content = """Title:
Authors:
Table:
================================================================================
Byte-by-byte Description of file: tab.txt
--------------------------------------------------------------------------------
   Bytes Format Units          		Label      Explanations
--------------------------------------------------------------------------------
   1- 10 A10    ---            		ID         ID
  12- 21 F10.5  10+3J/m/s/kpc2    	SBCONT     Cont surface brightness
  23- 32 F10.5  10-7J/s/kpc2 		SBLINE     Line surface brightness
--------------------------------------------------------------------------------
ID0001     70.99200   38.51040      
ID0001     13.05120   28.19240      
ID0001     3.83610    10.98370      
ID0001     1.99101    6.78822       
ID0001     1.31142    5.01932      
"""

    # Write to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(mrt_content)
        temp_path = f.name

    try:
        from astropy.table import Table
        from astropy import units as u

        # Read the table using the CDS format
        dat = Table.read(temp_path, format='ascii.cds')

        # Check the units for SBCONT column
        # Expected: 10+3 J / (m * s * kpc**2) which is equivalent to 1e3 * J / (m * s * kpc**2)
        # The issue states that the order of division is jumbled.
        # Correct parsing of "10+3J/m/s/kpc2" should be:
        # 10^3 * J * m^-1 * s^-1 * kpc^-2
        
        sbcont_unit = dat['SBCONT'].unit
        sbline_unit = dat['SBLINE'].unit

        # Let's decompose the units to check their structure
        # For SBCONT: expected is J / (m * s * kpc**2) with a factor of 1000
        # For SBLINE: expected is J / (s * kpc**2) with a factor of 1e-7
        
        # We check if the units are equivalent to the expected physical units.
        # SBCONT: 10+3 J/m/s/kpc2 -> 1000 * J / (m * s * kpc**2)
        expected_sbcont = 1e3 * u.J / (u.m * u.s * u.kpc**2)
        
        # SBLINE: 10-7 J/s/kpc2 -> 1e-7 * J / (s * kpc**2)
        expected_sbline = 1e-7 * u.J / (u.s * u.kpc**2)

        # Check equivalence
        # Note: unit equivalence checks if they represent the same physical quantity
        # We also want to ensure the scale factor is correct.
        
        assert sbcont_unit.is_equivalent(expected_sbcont), \
            f"SBCONT unit {sbcont_unit} is not equivalent to {expected_sbcont}"
        
        # Check the scale factor by converting a value of 1 in the parsed unit to the expected unit
        # If the units are identical (including scale), this should be 1.0
        scale_sbcont = (1 * sbcont_unit).to_value(expected_sbcont)
        assert abs(scale_sbcont - 1.0) < 1e-9, \
            f"SBCONT unit scale factor is incorrect: {scale_sbcont} instead of 1.0"

        assert sbline_unit.is_equivalent(expected_sbline), \
            f"SBLINE unit {sbline_unit} is not equivalent to {expected_sbline}"
        
        scale_sbline = (1 * sbline_unit).to_value(expected_sbline)
        assert abs(scale_sbline - 1.0) < 1e-9, \
            f"SBLINE unit scale factor is incorrect: {scale_sbline} instead of 1.0"

        print("Units are parsed correctly.")
        sys.exit(0)

    except AssertionError as e:
        print(f"Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

if __name__ == '__main__':
    main()
