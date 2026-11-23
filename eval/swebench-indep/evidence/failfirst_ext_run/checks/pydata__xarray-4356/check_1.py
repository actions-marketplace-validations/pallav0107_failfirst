import sys
import xarray as xr

def main():
    # Create a DataArray with some data
    da = xr.DataArray([[1., 2, 3], [4, 5, 6]])
    
    # The issue states that sum with min_count errors when passing more than one dim
    # We try to perform the operation that was reported as broken
    try:
        result = da.sum(["dim_0", "dim_1"], min_count=1)
        # If we get here without an exception, the fix is working
        # Let's verify the result is correct
        # Sum of all elements: 1+2+3+4+5+6 = 21
        expected_value = 21.0
        assert float(result.values) == expected_value, f"Expected {expected_value}, got {result.values}"
        sys.exit(0)
    except Exception as e:
        # If an exception occurs, the bug is still present
        print(f"Error occurred (bug likely still present): {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
