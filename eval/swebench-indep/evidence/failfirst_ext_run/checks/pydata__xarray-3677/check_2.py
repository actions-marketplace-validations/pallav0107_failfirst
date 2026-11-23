import xarray as xr

# Reproduce the issue: merging a DataArray into a Dataset using the dataset method
ds = xr.Dataset({'a': 0})
da = xr.DataArray(1, name='b')

# This should work according to the issue report (top-level merge works)
expected = xr.merge([ds, da])

# This was failing in the bug report with AttributeError: 'DataArray' object has no attribute 'items'
# If the bug is fixed, this should not raise an exception and should produce the same result as xr.merge
actual = ds.merge(da)

# Verify that the result is correct
assert 'a' in actual.data_vars
assert 'b' in actual.data_vars
assert actual['a'].values == 0
assert actual['b'].values == 1

print("Test passed: ds.merge(da) works correctly.")
