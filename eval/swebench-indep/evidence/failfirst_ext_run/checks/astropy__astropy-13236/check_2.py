import numpy as np
from astropy.table import Table, Column

# Create a structured numpy array
structured_data = np.array([(1, 2.0), (3, 4.0)], dtype=[('a', 'i4'), ('b', 'f8')])

# Add it to a Table
t = Table()
t['col'] = structured_data

# Check the type of the column added
col = t['col']

# The issue proposes that in version 5.2+, structured arrays should be added as Column,
# not auto-transformed into NdarrayMixin.
# If the fix is applied, col should be an instance of Column, not NdarrayMixin.
# Note: NdarrayMixin is a mixin class, so we check if it's specifically wrapped as such
# or if it remains a standard Column with structured dtype.

# In the fixed behavior, adding a structured array directly should result in a Column
# object that holds the structured array, rather than viewing it as an NdarrayMixin.

# Let's check if the column is a standard Column instance.
# Before the fix, it would be viewed as NdarrayMixin.
# After the fix, it should be a Column.

assert isinstance(col, Column), f"Expected Column, but got {type(col)}"

# Additionally, verify that the data inside is still the structured array
assert col.dtype == structured_data.dtype, "Dtype mismatch"
assert np.array_equal(col.as_array(), structured_data), "Data mismatch"

print("Check passed: Structured array is correctly handled as Column.")
