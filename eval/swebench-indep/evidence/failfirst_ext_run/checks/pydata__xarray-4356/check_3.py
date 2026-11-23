import sys
import xarray as xr

def main():
    # Create a DataArray as described in the issue
    da = xr.DataArray([[1., 2, 3], [4, 5, 6]])
    
    # The issue states that sum with min_count errors when passing more than one dim.
    # If fixed, this should not raise an error and should return the correct sum.
    try:
        result = da.sum(["dim_0", "dim_1"], min_count=1)
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)
        
    # The sum of all elements is 1+2+3+4+5+6 = 21.0
    expected_sum = 21.0
    
    # Check if the result is correct
    assert float(result) == expected_sum, f"Expected {expected_sum}, got {float(result)}"
    
    # Also test with min_count that should result in NaN if not enough valid values
    # Create an array with some NaNs
    import numpy as np
    da_nan = xr.DataArray([[1., np.nan, 3], [np.nan, 5, 6]])
    
    # Sum with min_count=4 should be NaN because there are only 4 valid values total, 
    # but we are summing over all dims. Wait, min_count applies to the number of non-NaN values.
    # Total valid values = 4 (1, 3, 5, 6). So min_count=4 should give sum=15.
    result_nan = da_nan.sum(["dim_0", "dim_1"], min_count=4)
    assert float(result_nan) == 15.0, f"Expected 15.0, got {float(result_nan)}"
    
    # min_count=5 should give NaN because there are only 4 valid values
    result_nan2 = da_nan.sum(["dim_0", "dim_1"], min_count=5)
    assert np.isnan(float(result_nan2)), f"Expected NaN, got {float(result_nan2)}"
    
    sys.exit(0)

if __name__ == "__main__":
    main()
