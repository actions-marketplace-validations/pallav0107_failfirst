from sympy.physics.quantum.dagger import Dagger
from sympy.physics.quantum.operator import Operator
from sympy.physics.quantum import IdentityOperator

# Create an operator A
A = Operator('A')

# Create the identity operator
Identity = IdentityOperator()

# Test 1: A * Identity should simplify to A
result1 = A * Identity
assert result1 == A, f"A * Identity should simplify to A, but got {result1}"

# Test 2: Dagger(A) * Identity should simplify to Dagger(A)
B = Dagger(A)
result2 = B * Identity
assert result2 == B, f"Dagger(A) * Identity should simplify to Dagger(A), but got {result2}"

print("All checks passed.")
