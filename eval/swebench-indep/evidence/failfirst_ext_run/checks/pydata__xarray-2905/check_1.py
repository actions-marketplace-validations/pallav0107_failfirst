import xarray as xr
import numpy as np

class HasValues(object):
    values = 5

# Create a DataArray with object dtype to store arbitrary objects
bad_indexed = xr.DataArray([None])

# Assign an instance of HasValues using .loc indexing
bad_indexed.loc[{'dim_0': 0}] = HasValues()

# Retrieve the stored value
stored_value = bad_indexed.values[0]

# The issue is that xarray incorrectly coerces the object because it has a .values attribute.
# Expected behavior: stored_value should be the HasValues instance itself.
# Buggy behavior: stored_value becomes an array containing the .values attribute (i.e., array(5)).

# Check if the stored value is indeed the HasValues instance
assert isinstance(stored_value, HasValues), f"Expected HasValues instance, got {type(stored_value)}: {stored_value}"

# Additionally check that it's not an array
assert not isinstance(stored_value, np.ndarray), f"Expected HasValues instance, but got numpy array: {stored_value}"

print("Check passed: Object with .values property was stored correctly without coercion.")
