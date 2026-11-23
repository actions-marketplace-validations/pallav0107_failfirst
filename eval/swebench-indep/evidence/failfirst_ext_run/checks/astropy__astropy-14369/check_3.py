import tempfile
import os
import sys

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
        temp_file = f.name

    try:
        from astropy.table import Table
        
        # Read the table using the CDS format
        dat = Table.read(temp_file, format='ascii.cds')
        
        # Get the units for the columns
        sbcont_unit = dat['SBCONT'].unit
        sbline_unit = dat['SBLINE'].unit
        
        # Convert units to string representation for comparison
        # The issue states that the order of division is jumbled.
        # Expected for SBCONT: 10+3 J / (m s kpc2) or equivalent canonical form
        # Expected for SBLINE: 10-7 J / (s kpc2) or equivalent canonical form
        
        # Let's check the physical type and the decomposition to ensure correctness.
        # The core issue is parsing "10+3J/m/s/kpc2" correctly.
        # In CDS format, "/" applies to all subsequent units until the end or another operator.
        # So "J/m/s/kpc2" means J / (m * s * kpc^2).
        
        # Let's verify by checking if the unit is equivalent to the expected SI-based composite.
        # For SBCONT: 10^3 J / (m * s * kpc^2)
        # For SBLINE: 10^-7 J / (s * kpc^2)
        
        # We can check this by constructing the expected unit and comparing equivalence.
        from astropy import units as u
        
        # Construct expected units
        # Note: kpc is kiloparsec. kpc2 means kpc**2.
        expected_sbcont_unit = 1e3 * u.J / (u.m * u.s * u.kpc**2)
        expected_sbline_unit = 1e-7 * u.J / (u.s * u.kpc**2)
        
        # Check equivalence
        # is_equivalent might fail if scales are different but we want exact match including scale
        # Let's check if they are physically equivalent and the scale matches.
        
        assert sbcont_unit.is_equivalent(expected_sbcont_unit), \
            f"SBCONT unit {sbcont_unit} is not equivalent to {expected_sbcont_unit}"
        
        # Check the scale factor explicitly
        # Convert both to the same base unit and compare values
        sbcont_in_base = sbcont_unit.to(u.J / (u.m * u.s * u.kpc**2))
        expected_sbcont_in_base = expected_sbcont_unit.to(u.J / (u.m * u.s * u.kpc**2))
        
        # The numerical factor should be 1.0 if they are identical
        assert abs(sbcont_in_base - 1.0) < 1e-9, \
            f"SBCONT unit scale mismatch: {sbcont_in_base} vs 1.0"

        assert sbline_unit.is_equivalent(expected_sbline_unit), \
            f"SBLINE unit {sbline_unit} is not equivalent to {expected_sbline_unit}"
            
        sbline_in_base = sbline_unit.to(u.J / (u.s * u.kpc**2))
        expected_sbline_in_base = expected_sbline_unit.to(u.J / (u.s * u.kpc**2))
        
        assert abs(sbline_in_base - 1.0) < 1e-9, \
            f"SBLINE unit scale mismatch: {sbline_in_base} vs 1.0"
            
        print("Units parsed correctly.")
        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file):
            os.unlink(temp_file)

if __name__ == '__main__':
    main()
