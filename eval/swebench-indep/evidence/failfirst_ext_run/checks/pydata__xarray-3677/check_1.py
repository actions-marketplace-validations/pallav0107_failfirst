import xarray as xr

# Reproduce the issue: merging a DataArray into a Dataset using the Dataset.merge() method
ds = xr.Dataset({'a': 0})
da = xr.DataArray(1, name='b')

# This should work after the fix
result = ds.merge(da)

# Verify the result contains both variables
assert 'a' in result.data_vars
assert 'b' in result.data_vars
assert result['a'].item() == 0
assert result['b'].item() == 1

print("Check passed: ds.merge(da) works correctly.")
