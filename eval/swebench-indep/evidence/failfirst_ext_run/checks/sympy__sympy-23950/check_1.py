from sympy import Contains, Reals, Symbol

x = Symbol('x')

# The issue states that Contains(x, Reals).as_set() returns Contains(x, Reals)
# which is wrong because Contains is a boolean, not a set.
# If fixed, .as_set() should return a proper Set object (likely Reals itself or an Intersection/Union involving it)
# and crucially, the result must have the as_relational method.

expr = Contains(x, Reals)
result = expr.as_set()

# Check 1: The result should not be a Contains object
assert not isinstance(result, Contains), f"as_set() returned a Contains object: {result}"

# Check 2: The result must have as_relational attribute (since it's supposed to be a Set)
assert hasattr(result, 'as_relational'), f"Result {result} of type {type(result)} does not have as_relational method"

# Check 3: Verify the specific failure case mentioned in the issue works now
# Piecewise((6, Contains(x, Reals)), (7, True))
# This internally calls c.as_set().as_relational(x)
from sympy.functions.elementary.piecewise import Piecewise
try:
    pw = Piecewise((6, Contains(x, Reals)), (7, True))
except AttributeError as e:
    raise AssertionError(f"Piecewise creation failed with AttributeError: {e}")

exit(0)
