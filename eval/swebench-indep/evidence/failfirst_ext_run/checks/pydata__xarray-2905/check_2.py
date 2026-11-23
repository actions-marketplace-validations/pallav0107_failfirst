import xarray as xr
import numpy as np

class HasValues(object):
    values = 5

# Create a DataArray with object dtype to hold arbitrary Python objects
bad_indexed = xr.DataArray([None], dims=['dim_0'])

# Assign an instance of HasValues to the first element
bad_indexed.loc[{'dim_0': 0}] = HasValues()

# Retrieve the value
val = bad_indexed.values[0]

# Check that the stored value is the HasValues instance, not coerced to an array
assert isinstance(val, HasValues), f"Expected HasValues instance, got {type(val)}: {val}"

# Also verify it's not an numpy array containing the value 5
assert not isinstance(val, np.ndarray), f"Value was coerced to ndarray: {val}"

print("Check passed: Object with .values property stored correctly.")
