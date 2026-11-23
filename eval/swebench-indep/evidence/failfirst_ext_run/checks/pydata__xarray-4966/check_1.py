import numpy as np
import xarray as xr
from xarray.core.variable import Variable
from xarray.coding.variables import decode_cf_variable

def test_unsigned_false_handling():
    """
    Test that xarray correctly handles the _Unsigned=False attribute for unsigned integer types.
    
    The issue states that OPeNDAP only knows unsigned bytes, but a hack exists where
    _Unsigned=False is added to indicate that the data should be treated as signed.
    
    When engine="pydap" is used, the data comes in as unsigned integers (e.g., uint8).
    If _Unsigned=False is present, xarray should convert these unsigned integers to 
    signed integers (e.g., int8) by interpreting the bit pattern as signed.
    
    For example:
    - uint8 value 255 should become int8 value -1
    - uint8 value 128 should become int8 value -128
    - uint8 value 0 should remain 0
    - uint8 value 127 should remain 127
    """
    
    # Create test data that mimics what pydap would return: unsigned integers
    # with the _Unsigned=False attribute indicating they should be treated as signed.
    
    # Test case 1: uint8 data with _Unsigned=False
    # Values: [128, 255, 0, 1, 2, 127] 
    # Expected signed interpretation: [-128, -1, 0, 1, 2, 127]
    unsigned_data = np.array([128, 255, 0, 1, 2, 127], dtype=np.uint8)
    
    var = Variable(
        dims=['test'],
        data=unsigned_data,
        attrs={'_Unsigned': 'False'}
    )
    
    # Decode the variable using xarray's CF decoding logic
    decoded_var = decode_cf_variable('test', var)
    
    # The decoded data should be signed integers
    # Check that the dtype is now a signed integer type
    assert decoded_var.dtype.kind == 'i', f"Expected signed integer dtype, got {decoded_var.dtype}"
    
    # Check specific values
    expected_signed = np.array([-128, -1, 0, 1, 2, 127], dtype=np.int8)
    np.testing.assert_array_equal(decoded_var.values, expected_signed, 
                                   err_msg=f"Values mismatch: got {decoded_var.values}, expected {expected_signed}")
    
    # Test case 2: uint16 data with _Unsigned=False
    # Value 65535 (0xFFFF) should become -1 in int16
    unsigned_data_16 = np.array([65535, 0, 32768, 32767], dtype=np.uint16)
    
    var_16 = Variable(
        dims=['test'],
        data=unsigned_data_16,
        attrs={'_Unsigned': 'False'}
    )
    
    decoded_var_16 = decode_cf_variable('test', var_16)
    
    assert decoded_var_16.dtype.kind == 'i', f"Expected signed integer dtype, got {decoded_var_16.dtype}"
    
    expected_signed_16 = np.array([-1, 0, -32768, 32767], dtype=np.int16)
    np.testing.assert_array_equal(decoded_var_16.values, expected_signed_16,
                                   err_msg=f"Values mismatch: got {decoded_var_16.values}, expected {expected_signed_16}")
    
    # Test case 3: Ensure _Unsigned=True still works correctly (existing behavior)
    # uint8 value 255 with _Unsigned=True should remain 255 (but might be upcast to larger int)
    unsigned_data_true = np.array([255, 128, 0], dtype=np.uint8)
    
    var_true = Variable(
        dims=['test'],
        data=unsigned_data_true,
        attrs={'_Unsigned': 'True'}
    )
    
    decoded_var_true = decode_cf_variable('test', var_true)
    
    # With _Unsigned=True, the values should remain as positive integers
    # The exact dtype may vary, but values should be preserved
    np.testing.assert_array_equal(decoded_var_true.values, unsigned_data_true.astype(decoded_var_true.dtype),
                                   err_msg=f"Values mismatch for _Unsigned=True: got {decoded_var_true.values}")
    
    print("All tests passed!")

if __name__ == "__main__":
    test_unsigned_false_handling()
