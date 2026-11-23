from sympy import ring, ZZ, symbols

# Reproduce the issue as described
R, x, y, z = ring("x,y,z", ZZ)
f = 3*x**2*y - x*y*z + 7*z**3 + 1

# Define new symbols to use in the expression
U, V, W = symbols("u,v,w")

# Call as_expr with the new symbols
expr = f.as_expr(U, V, W)

# The issue states that currently it ignores the passed symbols and uses self.ring.symbols (x, y, z)
# If fixed, it should use U, V, W instead.

# Check if the resulting expression contains the new symbols U, V, W
# and does not contain the old symbols x, y, z from the ring

# Get the free symbols of the resulting expression
free_syms = expr.free_symbols

# The correct behavior is that the expression is in terms of U, V, W
assert U in free_syms, f"Expected U in free symbols, got {free_syms}"
assert V in free_syms, f"Expected V in free symbols, got {free_syms}"
assert W in free_syms, f"Expected W in free symbols, got {free_syms}"

# The old symbols x, y, z should NOT be in the free symbols
assert x not in free_syms, f"Unexpected x in free symbols, got {free_syms}"
assert y not in free_syms, f"Unexpected y in free symbols, got {free_syms}"
assert z not in free_syms, f"Unexpected z in free symbols, got {free_syms}"

# Additionally, check the actual structure:
# f = 3*x**2*y - x*y*z + 7*z**3 + 1
# With U, V, W mapping to x, y, z respectively:
# Expected: 3*U**2*V - U*V*W + 7*W**3 + 1
expected_expr = 3*U**2*V - U*V*W + 7*W**3 + 1
assert expr == expected_expr, f"Expected {expected_expr}, got {expr}"

print("Check passed: PolyElement.as_expr() correctly accepts and uses provided symbols.")
