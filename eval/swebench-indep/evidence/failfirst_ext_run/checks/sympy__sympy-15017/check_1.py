import sympy

# Create a rank-0 array (scalar) as described in the issue
a = sympy.Array(3)

# The issue states that len(a) returns 0, but it should return 1
# because it has one element, consistent with numpy and the iterator length.

# Check that the length is 1
assert len(a) == 1, f"Expected len(a) to be 1 for a rank-0 array, but got {len(a)}"

# Also verify consistency with the iterator length mentioned in the issue
assert len(list(a)) == 1, f"Expected len(list(a)) to be 1, but got {len(list(a))}"

print("Check passed: len of rank-0 array is correctly 1.")
