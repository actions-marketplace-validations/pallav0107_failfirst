from sympy.physics.quantum.dagger import Dagger
from sympy.physics.quantum.operator import Operator
from sympy.physics.quantum import IdentityOperator

# Create an operator A
A = Operator('A')

# Create the identity operator
Identity = IdentityOperator()

# Check that A * Identity simplifies to A (this is reported as working)
result1 = A * Identity
assert result1 == A, f"A * Identity should simplify to A, but got {result1}"

# Create the dagger of A
B = Dagger(A)

# Check that B * Identity simplifies to B (this is reported as broken)
result2 = B * Identity
assert result2 == B, f"Dagger(A) * Identity should simplify to Dagger(A), but got {result2}"

print("All checks passed.")
