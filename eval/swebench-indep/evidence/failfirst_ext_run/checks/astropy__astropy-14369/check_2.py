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
        temp_filename = f.name

    try:
        from astropy.table import Table
        
        # Read the table using the CDS format
        dat = Table.read(temp_filename, format='ascii.cds')
        
        # Get the units for the columns
        sbcont_unit = dat['SBCONT'].unit
        sbline_unit = dat['SBLINE'].unit
        
        # Convert units to string representation for comparison
        # The issue states that the order of division is jumbled.
        # Expected for SBCONT: 1e+3 J / (m s kpc2) or equivalent canonical form
        # Expected for SBLINE: 1e-7 J / (s kpc2) or equivalent canonical form
        
        # Let's check the physical type and the structure of the unit.
        # The bug report shows:
        # SBCONT came out as: 1e+3 J s / (kpc2 m) -> This is WRONG because 's' is in numerator
        # SBLINE came out as: 1e-7 J kpc2 / s -> This is WRONG because 'kpc2' is in numerator
        
        # Correct interpretation of "10+3J/m/s/kpc2":
        # J / m / s / kpc^2 = J * m^-1 * s^-1 * kpc^-2
        
        # Correct interpretation of "10-7J/s/kpc2":
        # J / s / kpc^2 = J * s^-1 * kpc^-2
        
        # We can check if the unit is equivalent to the expected unit.
        
        from astropy import units as u
        
        # Define expected units
        # Note: kpc2 in CDS usually means kpc^2. Astropy should parse kpc2 as kpc**2.
        expected_sbcont_unit = 1e3 * u.J / (u.m * u.s * u.kpc**2)
        expected_sbline_unit = 1e-7 * u.J / (u.s * u.kpc**2)
        
        # Check equivalence
        # If the units are not equivalent, it means the parsing was incorrect.
        
        assert sbcont_unit.is_equivalent(expected_sbcont_unit), \
            f"SBCONT unit {sbcont_unit} is not equivalent to expected {expected_sbcont_unit}"
        
        assert sbline_unit.is_equivalent(expected_sbline_unit), \
            f"SBLINE unit {sbline_unit} is not equivalent to expected {expected_sbline_unit}"
            
        # Additionally, we can check the string representation to ensure it's not the broken one
        # but equivalence is the most robust check for physical correctness.
        
        print("Units are parsed correctly.")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # Clean up temporary file
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)

if __name__ == '__main__':
    main()
