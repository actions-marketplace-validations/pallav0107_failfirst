import sys
from sympy import symbols, sqf_list

def main():
    x = symbols('x')
    
    # Construct the polynomial as described in the issue:
    # (x**2 + 1) * (x - 1)**2 * (x - 2)**3 * (x - 3)**3
    poly = (x**2 + 1) * (x - 1)**2 * (x - 2)**3 * (x - 3)**3
    
    # Get the square-free factorization list
    coeff, factors = sqf_list(poly)
    
    # The issue states that the output should be consistent.
    # Specifically, it complains about getting two factors of multiplicity 3 
    # for (x-2) and (x-3), implying they might be merged or handled incorrectly 
    # in some versions, but let's look at what "correct" means.
    
    # A square-free factorization of a polynomial P is a list of pairs (f_i, m_i)
    # such that P = c * prod(f_i ** m_i) where each f_i is square-free and 
    # gcd(f_i, f_j) = 1 for i != j.
    
    # The polynomial is:
    # (x^2+1)^1 * (x-1)^2 * (x-2)^3 * (x-3)^3
    
    # The factors (x-2) and (x-3) are distinct irreducible polynomials.
    # They are both square-free.
    # Their multiplicities are 3 and 3 respectively.
    
    # The issue reporter says: "we should have (x*_2 - 5_x + 6, 3) and not 2 factors of multiplicity 3."
    # Wait, (x-2)(x-3) = x^2 - 5x + 6.
    # If the implementation merges factors with the same multiplicity, it might produce:
    # [(x^2+1, 1), (x-1, 2), ((x-2)*(x-3), 3)] which is [(x^2+1, 1), (x-1, 2), (x^2-5x+6, 3)]
    
    # Let's check what SymPy actually does. In standard SQF algorithms, 
    # factors are usually kept separate if they are coprime. However, some implementations 
    # or definitions might group by exponent. 
    # The issue title is "sqf and sqf_list output is not consistant".
    # The reporter claims the first example is "wrong" because it lists (x-3, 3) and (x-2, 3) separately,
    # and implies they should be combined into (x^2-5x+6, 3).
    
    # However, looking at the second example:
    # sqf_list( x**5 - 2*x**4 - 2*x**3 + 4*x**2 + x - 2 )
    # Output: (1, [(x - 2, 1), (x**2 - 1, 2)])
    # Here x^2-1 = (x-1)(x+1). So (x-1) and (x+1) are combined into x^2-1 because they both have multiplicity 2?
    # Let's expand x**5 - 2*x**4 - 2*x**3 + 4*x**2 + x - 2
    # Roots: 1, -1, 2. 
    # (x-1)(x+1)(x-2) = (x^2-1)(x-2) = x^3 - 2x^2 - x + 2
    # Squaring the part with multiplicity 2? 
    # If the polynomial is (x-2)^1 * (x-1)^2 * (x+1)^2 = (x-2) * ((x-1)(x+1))^2 = (x-2)(x^2-1)^2
    # Expanding: (x-2)(x^4 - 2x^2 + 1) = x^5 - 2x^4 - 2x^3 + 4x^2 + x - 2. Yes.
    # So in the second example, factors with the same multiplicity (2) were combined into a single square-free polynomial.
    
    # Therefore, the "correct" behavior implied by the issue is that factors with the same multiplicity 
    # should be combined into a single square-free factor.
    
    # So for the first example:
    # (x^2+1) has mult 1.
    # (x-1) has mult 2.
    # (x-2) has mult 3.
    # (x-3) has mult 3.
    
    # Expected correct output according to the issue's logic (consistency with example 2):
    # Multiplicity 1: x^2+1
    # Multiplicity 2: x-1
    # Multiplicity 3: (x-2)*(x-3) = x^2 - 5x + 6
    
    # So the factors list should be:
    # [(x^2+1, 1), (x-1, 2), (x^2-5x+6, 3)]
    # Note: The order might vary, but typically it's sorted by multiplicity or degree. 
    # In the second example, the order was [(x-2, 1), (x^2-1, 2)], i.e., increasing multiplicity.
    
    # Let's construct the expected factors.
    # We need to verify if the current output matches this "combined" format.
    
    # Current output reported in issue: (1, [(x**2 + 1, 1), (x - 1, 2), (x - 3, 3), (x - 2, 3)])
    # This is UNCOMBINED.
    
    # Desired output: (1, [(x**2 + 1, 1), (x - 1, 2), (x**2 - 5*x + 6, 3)])
    
    # Let's check if the installed version behaves correctly (i.e., combines them).
    
    # Normalize the factors for comparison: sort by multiplicity, then by the polynomial expression.
    # Actually, just checking if there is a factor with multiplicity 3 that equals (x-2)*(x-3) is key.
    
    # Let's get the actual result
    actual_factors = dict(factors)
    
    # Check if multiplicities are combined.
    # If combined, there should be exactly one factor with multiplicity 3.
    # If uncombined, there will be two factors with multiplicity 3.
    
    multis = [m for f, m in factors]
    
    # Count how many factors have multiplicity 3
    count_mult_3 = sum(1 for m in multis if m == 3)
    
    # If the bug is fixed, factors with same multiplicity should be combined.
    # So there should be only 1 factor with multiplicity 3, which is (x-2)*(x-3).
    
    # However, we must be careful. Does SymPy always combine them?
    # The issue says the second example IS correct (combined).
    # So the fix should make the first example also combine.
    
    # Assert that there is only one factor with multiplicity 3
    assert count_mult_3 == 1, f"Expected 1 factor with multiplicity 3, but found {count_mult_3}. Factors: {factors}"
    
    # Find that factor
    factor_mult_3 = [f for f, m in factors if m == 3][0]
    
    # It should be equal to (x-2)*(x-3) = x^2 - 5x + 6
    expected_factor_mult_3 = x**2 - 5*x + 6
    
    assert factor_mult_3 == expected_factor_mult_3, f"Expected factor {expected_factor_mult_3} with multiplicity 3, but got {factor_mult_3}"
    
    # Also check other factors for completeness
    # Multiplicity 1: x^2 + 1
    # Multiplicity 2: x - 1
    
    # Create a dict for easier lookup
    factor_dict = {f: m for f, m in factors}
    
    # Check x^2 + 1 has multiplicity 1
    assert (x**2 + 1) in factor_dict, "Missing factor x^2+1"
    assert factor_dict[x**2 + 1] == 1, f"Expected multiplicity 1 for x^2+1, got {factor_dict[x**2+1]}"
    
    # Check x - 1 has multiplicity 2
    assert (x - 1) in factor_dict, "Missing factor x-1"
    assert factor_dict[x - 1] == 2, f"Expected multiplicity 2 for x-1, got {factor_dict[x-1]}"
    
    # If all assertions pass, the behavior is correct (fixed).
    sys.exit(0)

if __name__ == "__main__":
    main()
