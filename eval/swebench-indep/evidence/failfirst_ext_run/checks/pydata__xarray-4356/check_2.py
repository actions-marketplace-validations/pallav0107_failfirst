import xarray as xr

# Reproduce the issue: sum with min_count should work with multiple dimensions
da = xr.DataArray([[1., 2, 3], [4, 5, 6]])

# This should not raise an error if the bug is fixed
result = da.sum(["dim_0", "dim_1"], min_count=1)

# The expected result is the sum of all elements: 1+2+3+4+5+6 = 21.0
expected = 21.0

assert result.item() == expected, f"Expected {expected}, got {result.item()}"

print("Check passed: min_count works with multiple dimensions")
