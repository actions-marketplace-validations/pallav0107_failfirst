import numpy as np
import xarray as xr

# Reproduce the issue from the bug report
da = xr.DataArray(np.arange(24), dims=["time"])
da = da.assign_coords(day=365 * da)
ds = da.to_dataset(name="T")

# Perform the coarsen construct operation
result = ds.coarsen(time=12).construct(time=("year", "month"))

# Check if 'day' is still a coordinate in the result
# The issue states that non-dimensional coordinates are demoted to variables.
# Expected behavior: 'day' should remain a coordinate.

assert "day" in result.coords, f"'day' should be a coordinate, but found in coords: {list(result.coords)} and data_vars: {list(result.data_vars)}"
assert "day" not in result.data_vars, f"'day' should not be a data variable, but found in data_vars: {list(result.data_vars)}"

print("Check passed: 'day' remains a coordinate after coarsen.construct")
