from sympy.physics.vector import ReferenceFrame

N = ReferenceFrame('N')

# The issue reports that sum([N.x, (0 * N.x)]) raises a TypeError.
# If the bug is fixed, this should work without raising an exception.
result = sum([N.x, (0 * N.x)])

# Verify the result is a Vector and equals N.x (since 0*N.x is the zero vector)
assert result == N.x, f"Expected N.x, got {result}"

exit(0)
