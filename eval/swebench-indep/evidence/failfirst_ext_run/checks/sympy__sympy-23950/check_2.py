from sympy import Contains, Reals, Symbol

x = Symbol('x')

# The issue states that Contains(x, Reals).as_set() incorrectly returns Contains(x, Reals)
# instead of a proper set object (like Reals or an Interval/Union representing the domain).
# A correct implementation should return a Set object.

result = Contains(x, Reals).as_set()

# Check 1: The result should not be a Contains object
assert not isinstance(result, Contains), f"as_set() returned a Contains object: {result}"

# Check 2: The result should have the as_relational method, which is required for Sets
# This was the secondary failure mentioned in the issue trace.
assert hasattr(result, 'as_relational'), f"Result {result} of type {type(result)} does not have as_relational method"

# If we reach here, the behavior is fixed.
exit(0)
