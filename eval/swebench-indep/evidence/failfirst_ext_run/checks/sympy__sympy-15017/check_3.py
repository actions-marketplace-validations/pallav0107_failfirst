import sympy

# Create a rank-0 array (scalar) as described in the issue
a = sympy.Array(3)

# The issue states that len(a) returns 0, but it should return 1
# because a scalar has one element.
# We assert that len(a) is 1 to verify the fix.
assert len(a) == 1, f"Expected len(a) to be 1 for a rank-0 array, but got {len(a)}"

# Additional check: ensure consistency with list conversion
assert len(list(a)) == 1, f"Expected len(list(a)) to be 1, but got {len(list(a))}"

print("Check passed: len of rank-0 array is correctly 1.")
