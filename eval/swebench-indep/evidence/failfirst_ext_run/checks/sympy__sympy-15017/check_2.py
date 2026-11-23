import sympy

# Create a rank-0 array (scalar) as described in the issue
a = sympy.Array(3)

# The issue states that len(a) returns 0, but it should return 1
# because it has one element.
# We assert that len(a) is 1 to check if the bug is fixed.
assert len(a) == 1, f"Expected len(a) to be 1 for a rank-0 array, but got {len(a)}"

# Also verify consistency with list conversion mentioned in the issue
assert len(list(a)) == 1, f"Expected len(list(a)) to be 1, but got {len(list(a))}"

exit(0)
