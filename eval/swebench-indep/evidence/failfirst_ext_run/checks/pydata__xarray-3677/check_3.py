import xarray as xr

# Reproduce the issue described in the bug report
ds = xr.Dataset({'a': 0})
da = xr.DataArray(1, name='b')

# This works fine according to the issue description
expected = xr.merge([ds, da])

# This should also work after the fix, but fails in the buggy version
# with AttributeError: 'DataArray' object has no attribute 'items'
try:
    result = ds.merge(da)
except AttributeError:
    # If we get an AttributeError, the bug is still present
    raise AssertionError("Bug is still present: ds.merge(da) raised AttributeError")

# Verify that the result matches the expected output from the top-level merge function
assert result.equals(expected), f"Result mismatch:\nExpected:\n{expected}\nGot:\n{result}"

print("Check passed: ds.merge(da) works correctly and matches xr.merge([ds, da])")
