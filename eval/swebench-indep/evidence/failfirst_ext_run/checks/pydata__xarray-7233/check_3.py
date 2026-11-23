import numpy as np
import xarray as xr

# Reproduce the issue from the bug report
da = xr.DataArray(np.arange(24), dims=["time"])
da = da.assign_coords(day=365 * da)
ds = da.to_dataset(name="T")

# Perform the coarsen construct operation
result = ds.coarsen(time=12).construct(time=("year", "month"))

# The issue states that 'day' is demoted from a coordinate to a variable.
# Expected behavior: 'day' should remain a coordinate.
# In xarray, coordinates are listed in ds.coords and non-coordinate data variables are in ds.data_vars.

# Check if 'day' is still a coordinate in the result
assert "day" in result.coords, f"'day' was demoted to a data variable. Coords: {list(result.coords)}, Data vars: {list(result.data_vars)}"

# Additionally, ensure it is NOT in data_vars
assert "day" not in result.data_vars, f"'day' incorrectly appears in data variables."

print("Check passed: 'day' remains a coordinate after coarsen.construct.")
