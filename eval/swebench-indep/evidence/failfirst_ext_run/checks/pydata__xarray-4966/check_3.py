import numpy as np
import xarray as xr
from xarray.coding.variables import decode_cf_variable
import warnings

def test_unsigned_false_handling():
    """
    Test that xarray correctly handles the _Unsigned=False attribute for unsigned byte data.
    
    According to the issue:
    - OPeNDAP only knows unsigned bytes.
    - A hack adds _Unsigned=False to indicate the data should be treated as signed.
    - netCDF4 engine handles this correctly (returns negative values).
    - pydap engine does not handle this, returning unsigned values (e.g., 128 instead of -128).
    
    The fix should make xarray treat unsigned data with _Unsigned=False as signed.
    """
    
    # Create a sample unsigned byte array that represents signed values
    # In unsigned bytes: 0-127 are positive, 128-255 represent -128 to -1
    # We'll create data that would be [-128, -1, 0, 1, 2, nan, 127] if interpreted as signed
    # But stored as unsigned bytes: [128, 255, 0, 1, 2, nan, 127]
    
    # Note: NaN cannot be represented in integer arrays, so we'll use a float array 
    # to simulate what pydap might return (since it doesn't handle the conversion)
    
    # Simulate raw data as unsigned bytes (what pydap returns without the fix)
    # Values: 128, 255, 0, 1, 2, 127 (we'll handle NaN separately)
    raw_data_unsigned = np.array([128, 255, 0, 1, 2, 127], dtype=np.uint8)
    
    # Expected signed interpretation: -128, -1, 0, 1, 2, 127
    expected_signed = np.array([-128, -1, 0, 1, 2, 127], dtype=np.float32)
    
    # Create a variable with _Unsigned=False attribute
    # This simulates what comes from pydap before decoding
    var = xr.Variable(
        dims=['test'],
        data=raw_data_unsigned.astype(np.float32),  # pydap often returns floats
        attrs={'_Unsigned': 'False'}
    )
    
    # Decode the variable using xarray's CF decoding
    # This should recognize _Unsigned=False and convert unsigned to signed
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        decoded_var = decode_cf_variable('test', var)
        
        # Check if there was a warning about ignoring _Unsigned attribute
        # If the fix is implemented, there should NOT be such a warning
        unsigned_warnings = [warning for warning in w if '_Unsigned' in str(warning.message)]
        
        # The fix should prevent the warning and correctly decode the values
        assert len(unsigned_warnings) == 0, f"Unexpected warning about _Unsigned attribute: {[str(w.message) for w in unsigned_warnings]}"
    
    # Check that the data has been correctly converted to signed values
    # The decoded data should match the expected signed values
    np.testing.assert_array_almost_equal(
        decoded_var.data[:6],  # Exclude NaN position for now
        expected_signed,
        decimal=1,
        err_msg=f"Data not correctly converted from unsigned to signed. Got {decoded_var.data[:6]}, expected {expected_signed}"
    )
    
    # Also test with a case that includes NaN handling
    # Create data with a fill value or mask for NaN
    raw_data_with_nan = np.array([128, 255, 0, 1, 2, 254, 127], dtype=np.uint8)  # Using 254 as a placeholder for NaN position
    expected_with_nan = np.array([-128, -1, 0, 1, 2, -2, 127], dtype=np.float32)
    
    var_with_nan = xr.Variable(
        dims=['test'],
        data=raw_data_with_nan.astype(np.float32),
        attrs={'_Unsigned': 'False', '_FillValue': 254}
    )
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        decoded_var_with_nan = decode_cf_variable('test', var_with_nan)
        unsigned_warnings = [warning for warning in w if '_Unsigned' in str(warning.message)]
        assert len(unsigned_warnings) == 0, f"Unexpected warning about _Unsigned attribute with NaN: {[str(w.message) for w in unsigned_warnings]}"
    
    # Check non-NaN values
    mask = decoded_var_with_nan.data != 254  # Assuming _FillValue is handled
    # Actually, let's just check the values directly since _FillValue handling might vary
    np.testing.assert_array_almost_equal(
        decoded_var_with_nan.data[[0, 1, 2, 3, 4, 6]],  # Skip the fill value position
        expected_with_nan[[0, 1, 2, 3, 4, 6]],
        decimal=1,
        err_msg=f"Data with NaN not correctly converted. Got {decoded_var_with_nan.data}, expected {expected_with_nan}"
    )

if __name__ == '__main__':
    test_unsigned_false_handling()
    print("All tests passed!")
