from sympy import ring, ZZ, symbols

# Reproduce the issue scenario
R, x, y, z = ring("x,y,z", ZZ)
f = 3*x**2*y - x*y*z + 7*z**3 + 1

# Define new symbols to use in the expression
U, V, W = symbols("u,v,w")

# Call as_expr with the new symbols
expr = f.as_expr(U, V, W)

# The issue states that passing U, V, W results in an expression still using x, y, z.
# If fixed, the expression should use u, v, w instead.

# Check if the resulting expression contains the new symbols and not the old ones
# We verify that the free symbols of the result are exactly {U, V, W}
assert expr.free_symbols == {U, V, W}, f"Expected free symbols to be {{U, V, W}}, but got {expr.free_symbols}. Expression: {expr}"

# Additionally, check that the old symbols are not present
assert x not in expr.free_symbols, "Old symbol x found in expression"
assert y not in expr.free_symbols, "Old symbol y found in expression"
assert z not in expr.free_symbols, "Old symbol z found in expression"

print("Check passed: as_expr correctly uses provided symbols.")
