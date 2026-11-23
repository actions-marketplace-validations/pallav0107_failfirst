import xarray as xr
import numpy as np

class HasValues(object):
    values = 5

# Create a DataArray with object dtype to store arbitrary objects
bad_indexed = xr.DataArray([None])

# Assign an instance of HasValues using .loc
bad_indexed.loc[{'dim_0': 0}] = HasValues()

# Retrieve the stored value
stored_value = bad_indexed.values[0]

# The issue states that if the RHS has a .values property, it gets coerced.
# Expected behavior: stored_value should be the HasValues instance itself.
# Buggy behavior: stored_value becomes array(5) because xarray accessed .values

# Check if the stored value is the original instance
assert isinstance(stored_value, HasValues), f"Expected HasValues instance, got {type(stored_value)}: {stored_value}"

# Additionally check that the .values attribute of the stored object is still 5
# and not that the object itself was replaced by the value 5 or an array containing 5
assert stored_value.values == 5, f"Expected stored_value.values to be 5, got {stored_value.values}"

# Ensure it's not a numpy array that happened to contain 5
assert not isinstance(stored_value, np.ndarray), f"Stored value should not be a numpy array, got {stored_value}"

print("Check passed: Behavior is correct.")
