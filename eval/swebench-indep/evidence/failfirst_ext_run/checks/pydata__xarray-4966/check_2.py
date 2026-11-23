import numpy as np
import xarray as xr
from xarray.coding.variables import _maybe_decode_cf_variable
import warnings

def test_unsigned_false_handling():
    """
    Test that xarray correctly handles the _Unsigned=False attribute for unsigned byte data.
    
    According to the issue:
    - OPeNDAP only knows unsigned bytes.
    - There is a convention/hack where _Unsigned=False is added to indicate that 
      unsigned bytes should be interpreted as signed bytes.
    - xarray should handle this symmetrically to how it handles _Unsigned=True.
    
    The fix should be in xarray/coding/variables.py around line 311.
    """
    
    # Create test data that simulates unsigned bytes with negative values when interpreted as signed
    # In unsigned bytes: 128-255 represent negative numbers when interpreted as signed (-128 to -1)
    # We'll create data that looks like unsigned bytes but should be interpreted as signed
    
    # Simulate raw unsigned byte data (0-255 range)
    raw_data = np.array([128, 255, 0, 1, 2, 255, 127], dtype=np.uint8)
    
    # Create a variable with _Unsigned=False attribute
    # This should tell xarray to interpret these unsigned bytes as signed bytes
    var = xr.Variable(
        dims=['test'],
        data=raw_data.astype(np.float32),  # pydap often returns float32 for bytes
        attrs={'_Unsigned': 'False'}
    )
    
    # Test the internal function that handles _Unsigned attribute
    # We need to check if the fix handles _Unsigned=False correctly
    
    # First, let's check what happens with the current implementation
    # by looking at the coding/variables.py logic
    
    # The issue mentions that the warning comes from conventions.py:492
    # and the fix should be in coding/variables.py around line 311
    
    # Let's create a more direct test by checking the decode_cf_variable behavior
    from xarray.conventions import decode_cf_variable
    
    # Create a variable similar to what pydap would return
    # pydap returns unsigned bytes as float32 with _Unsigned=False attribute
    test_var = xr.Variable(
        dims=['test'],
        data=np.array([128.0, 255.0, 0.0, 1.0, 2.0, 255.0, 127.0], dtype=np.float32),
        attrs={'_Unsigned': 'False'}
    )
    
    # Decode the variable - this should apply the signed interpretation
    decoded_var = decode_cf_variable('test', test_var)
    
    # If _Unsigned=False is handled correctly, the values should be interpreted as signed bytes
    # 128 -> -128, 255 -> -1, 0 -> 0, 1 -> 1, 2 -> 2, 255 -> -1, 127 -> 127
    expected_signed_values = np.array([-128.0, -1.0, 0.0, 1.0, 2.0, -1.0, 127.0], dtype=np.float32)
    
    # Check if the decoded values match the expected signed interpretation
    assert np.allclose(decoded_var.values, expected_signed_values), \
        f"Expected signed values {expected_signed_values}, but got {decoded_var.values}"
    
    # Also test that no warning is raised for _Unsigned=False on float types
    # (The original issue shows a warning being raised incorrectly)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        decoded_var2 = decode_cf_variable('test', test_var)
        # Filter for SerializationWarning about _Unsigned attribute
        unsigned_warnings = [warning for warning in w 
                           if 'SerializationWarning' in str(warning.category) 
                           and '_Unsigned' in str(warning.message)]
        assert len(unsigned_warnings) == 0, \
            f"Unexpected warning raised: {[str(w.message) for w in unsigned_warnings]}"

if __name__ == '__main__':
    test_unsigned_false_handling()
    print("Test passed: _Unsigned=False is handled correctly")
