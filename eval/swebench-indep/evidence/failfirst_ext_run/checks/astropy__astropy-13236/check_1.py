import numpy as np
from astropy.table import Table, Column
from astropy.utils.data_info import MixinInfo

# The issue proposes that in version 5.2 (the fixed state), 
# structured arrays should NOT be automatically transformed into NdarrayMixin.
# Instead, they should remain as regular Columns (or at least not be forced into NdarrayMixin).

# Create a structured numpy array
structured_data = np.array([(1, 2.0), (3, 4.0)], dtype=[('a', 'i4'), ('b', 'f8')])

# Add it to a Table
t = Table()
t['struct_col'] = structured_data

# Check the type of the column added
col = t['struct_col']

# In the "fixed" behavior (post-issue resolution):
# The column should ideally be a standard Column or MaskedColumn containing the structured array,
# NOT an instance of NdarrayMixin which was the old automatic behavior.
# However, looking at how astropy handles this, if it's treated as a normal column, 
# it will be an instance of Column. If it was converted to NdarrayMixin, it would be an instance of NdarrayMixin.

# Let's check if it is an NdarrayMixin. 
# The issue says: "Change the behavior in 5.2 by removing this clause."
# The clause was: data = data.view(NdarrayMixin)
# So if the fix is applied, col should NOT be an instance of NdarrayMixin.

from astropy.table.column import BaseColumn

# We need to verify that the column is NOT an NdarrayMixin.
# Note: In recent versions, structured arrays might just stay as Column objects with structured dtype.

is_mixin = isinstance(col, MixinInfo) or hasattr(col, '_info') and isinstance(col.info, MixinInfo)

# Actually, let's look at the class hierarchy.
# NdarrayMixin is a specific class in astropy.table.mixin_columns
from astropy.table.mixin_columns import NdarrayMixin

# If the bug is FIXED, the column should NOT be an instance of NdarrayMixin.
# It should be a regular Column (or subclass) that holds the structured array.

assert not isinstance(col, NdarrayMixin), f"Column should not be NdarrayMixin, but is {type(col)}"

# Additionally, ensure it is still accessible and has the right data
assert col.dtype.names == ('a', 'b'), "Column dtype names mismatch"
assert len(col) == 2, "Column length mismatch"

print("Check passed: Structured array is not auto-transformed to NdarrayMixin.")
