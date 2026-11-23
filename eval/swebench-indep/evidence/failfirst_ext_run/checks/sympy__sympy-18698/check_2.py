import sys
from sympy import symbols, sqf_list

def main():
    x = symbols('x')
    
    # The polynomial from the issue: (x**2 + 1) * (x - 1)**2 * (x - 2)**3 * (x - 3)**3
    poly = (x**2 + 1) * (x - 1)**2 * (x - 2)**3 * (x - 3)**3
    
    coeff, factors = sqf_list(poly)
    
    # Convert factors to a dictionary for easier checking
    # factors is a list of tuples (factor, multiplicity)
    factor_dict = {f.as_expr(): m for f, m in factors}
    
    # Expected behavior:
    # Each irreducible factor should appear exactly once with its correct multiplicity.
    # (x^2 + 1) has multiplicity 1
    # (x - 1) has multiplicity 2
    # (x - 2) has multiplicity 3
    # (x - 3) has multiplicity 3
    
    # Check that we have exactly 4 distinct factors
    assert len(factors) == 4, f"Expected 4 factors, got {len(factors)}: {factors}"
    
    # Check multiplicities
    # We need to match the factors correctly. Since SymPy might order them differently,
    # we check by matching the factor expression.
    
    found_x2_plus_1 = False
    found_x_minus_1 = False
    found_x_minus_2 = False
    found_x_minus_3 = False
    
    for factor, mult in factors:
        if factor == x**2 + 1:
            assert mult == 1, f"Expected multiplicity 1 for x**2 + 1, got {mult}"
            found_x2_plus_1 = True
        elif factor == x - 1:
            assert mult == 2, f"Expected multiplicity 2 for x - 1, got {mult}"
            found_x_minus_1 = True
        elif factor == x - 2:
            assert mult == 3, f"Expected multiplicity 3 for x - 2, got {mult}"
            found_x_minus_2 = True
        elif factor == x - 3:
            assert mult == 3, f"Expected multiplicity 3 for x - 3, got {mult}"
            found_x_minus_3 = True
        else:
            raise AssertionError(f"Unexpected factor: {factor}")
    
    assert found_x2_plus_1, "Factor x**2 + 1 not found"
    assert found_x_minus_1, "Factor x - 1 not found"
    assert found_x_minus_2, "Factor x - 2 not found"
    assert found_x_minus_3, "Factor x - 3 not found"
    
    print("All checks passed. The issue is fixed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
