import sys
from sympy import symbols, sqf_list

def main():
    x = symbols('x')
    
    # Construct the polynomial as described in the issue:
    # (x**2 + 1) * (x - 1)**2 * (x - 2)**3 * (x - 3)**3
    poly = (x**2 + 1) * (x - 1)**2 * (x - 2)**3 * (x - 3)**3
    
    # Get the square-free factorization
    coeff, factors = sqf_list(poly)
    
    # The issue states that the output should be consistent.
    # Specifically, it complains about getting two factors of multiplicity 3 
    # i.e., [(..., 3), (..., 3)] instead of combining them if they were the same base,
    # but here the bases are different (x-2 and x-3).
    
    # Let's look closely at the issue description again.
    # "The example below is wrong in the sense that we should have (x*_2 - 5_x + 6, 3) and not 2 factors of multiplicity 3."
    # This part of the issue description is slightly confusingly written ("x*_2 - 5_x + 6"). 
    # However, (x-2)*(x-3) = x^2 - 5x + 6.
    # The reporter seems to expect that (x-2)^3 * (x-3)^3 should be represented as ((x-2)*(x-3))^3 = (x^2 - 5x + 6)^3?
    # No, that's not how square-free factorization usually works over integers/rationals unless the factors are merged.
    # Square-free factorization decomposes f into c * f1^1 * f2^2 * ... where fi are square-free and pairwise coprime.
    # (x-2) and (x-3) are coprime. So (x-2)^3 * (x-3)^3 should appear as separate entries with multiplicity 3.
    # Wait, let's re-read carefully.
    # The reporter says: "we should have (x*_2 - 5_x + 6, 3) and not 2 factors of multiplicity 3."
    # This implies the reporter thinks (x-2)^3 * (x-3)^3 should be grouped into one factor (x^2-5x+6)^3.
    # But standard sqf_list returns coprime square-free factors. (x-2) and (x-3) are distinct linear factors.
    # They are already square-free. Their product is square-free. 
    # If we group them, we get (x^2-5x+6)^3. Is x^2-5x+6 square-free? Yes.
    # So both representations are mathematically valid decompositions into powers of square-free polynomials.
    # However, SymPy's sqf_list typically returns irreducible factors or at least coprime factors.
    
    # Let's look at the second example which is deemed "correct":
    # sqf_list( x**5 - 2*x**4 - 2*x**3 + 4*x**2 + x - 2 )
    # Result: (1, [(x - 2, 1), (x**2 - 1, 2)])
    # Note that x^2 - 1 = (x-1)(x+1). These are distinct linear factors, yet they are grouped into x^2-1 with multiplicity 2.
    # Why? Because in the original polynomial, (x-1)^2 * (x+1)^2 appears. 
    # SymPy's sqf_list does NOT necessarily split into irreducibles. It splits into square-free parts.
    # x^2-1 is square-free. (x-1) and (x+1) are also square-free.
    # The algorithm usually computes gcd(f, f') etc.
    
    # The inconsistency reported is:
    # In the first case: (x-2)^3 and (x-3)^3 are kept separate.
    # In the second case: (x-1)^2 and (x+1)^2 are merged into (x^2-1)^2.
    
    # If the behavior is "fixed", it likely means either:
    # 1. Both are merged (if possible/consistent)
    # 2. Both are split (into irreducibles)
    
    # Let's check what the current/fixed behavior should be.
    # Usually, users expect sqf_list to return factors that are square-free.
    # Merging (x-2) and (x-3) into (x^2-5x+6) is valid.
    # Splitting (x^2-1) into (x-1) and (x+1) is also valid.
    
    # The issue title is "sqf and sqf_list output is not consistant".
    # If the fix makes them consistent by splitting all into irreducibles:
    # Then the first example should have (x-2, 3) and (x-3, 3). (Which it does in the report)
    # And the second example should have (x-1, 2) and (x+1, 2). (But the report says it has (x^2-1, 2))
    
    # If the fix makes them consistent by merging where possible:
    # Then the first example should have (x^2-5x+6, 3).
    # And the second example has (x^2-1, 2).
    
    # Let's look at SymPy's actual behavior history.
    # In older versions, sqf_list might have been inconsistent depending on the domain or implementation details.
    # A common "fix" for consistency is to ensure that the factors returned are indeed square-free and coprime.
    # Both (x-2) and (x-3) are coprime. (x-1) and (x+1) are coprime.
    
    # Actually, looking at SymPy documentation and typical behavior:
    # sqf_list returns a list of (factor, exponent) where factor is square-free.
    # It does not guarantee irreducibility.
    # However, the inconsistency described suggests that one case merged coprime factors while the other didn't.
    
    # If the issue is considered "fixed", the behavior should be consistent.
    # Most likely, the expected correct behavior for `sqf_list` in SymPy is to return **coprime** square-free factors.
    # In the second example: (x-2) and (x^2-1) are coprime. Inside x^2-1, (x-1) and (x+1) are coprime.
    # Why were they merged? Maybe because they came from the same gcd step?
    
    # Let's assume the "correct" behavior is that distinct irreducible factors are NOT merged unless necessary.
    # Or conversely, that they ARE merged if they share the same exponent?
    
    # Let's test the specific assertion based on the issue reporter's claim of what is "wrong".
    # Reporter says: First example output `(1, [(x**2 + 1, 1), (x - 1, 2), (x - 3, 3), (x - 2, 3)])` is WRONG.
    # Reporter expects: `(x^2 - 5x + 6, 3)` instead of two factors of multiplicity 3.
    # This implies the reporter wants merging of factors with the same multiplicity.
    
    # Reporter says: Second example output `(1, [(x - 2, 1), (x**2 - 1, 2)])` is CORRECT.
    # Here, (x-1) and (x+1) were merged into (x^2-1) because they both had multiplicity 2.
    
    # So the "fixed" behavior should merge coprime square-free factors that have the same exponent.
    # Therefore, for the first example, (x-2)^3 and (x-3)^3 should be merged into (x^2-5x+6)^3.
    
    # Let's verify this logic. If the bug is fixed, sqf_list should merge factors with the same exponent.
    # Expected result for first poly:
    # Factors: (x^2+1)^1, (x-1)^2, (x-2)^3, (x-3)^3
    # Merge exponents 3: (x-2)*(x-3) = x^2 - 5x + 6.
    # So we should see (x^2 - 5x + 6, 3).
    # We should NOT see (x-2, 3) and (x-3, 3) separately.
    
    # Let's construct the check.
    # If the behavior is fixed, the factors list should contain (x**2 - 5*x + 6, 3).
    # It should NOT contain both (x-2, 3) and (x-3, 3).
    
    # Note: The order of factors in the list might vary.
    
    # Check if (x**2 - 5*x + 6, 3) is in the factors.
    target_factor = x**2 - 5*x + 6
    target_exp = 3
    
    found_merged = False
    for factor, exp in factors:
        if factor == target_factor and exp == target_exp:
            found_merged = True
            break
            
    # Also ensure that the separate factors are NOT present with exponent 3
    found_separate_2 = False
    found_separate_3 = False
    for factor, exp in factors:
        if factor == (x - 2) and exp == 3:
            found_separate_2 = True
        if factor == (x - 3) and exp == 3:
            found_separate_3 = True
            
    # If fixed, we expect merged to be True, and separate to be False.
    # If not fixed, we expect merged to be False, and separate to be True.
    
    # The script must exit 0 if correct (fixed).
    assert found_merged, "Expected merged factor (x**2 - 5*x + 6, 3) not found"
    assert not found_separate_2, "Unexpected separate factor (x - 2, 3) found"
    assert not found_separate_3, "Unexpected separate factor (x - 3, 3) found"
    
    # Additionally, check the other factors are present correctly
    # (x**2 + 1, 1) and (x - 1, 2)
    found_x2_1 = False
    found_x1_2 = False
    for factor, exp in factors:
        if factor == x**2 + 1 and exp == 1:
            found_x2_1 = True
        if factor == x - 1 and exp == 2:
            found_x1_2 = True
            
    assert found_x2_1, "Expected factor (x**2 + 1, 1) not found"
    assert found_x1_2, "Expected factor (x - 1, 2) not found"
    
    # Check coefficient
    assert coeff == 1, "Expected coefficient 1"

    sys.exit(0)

if __name__ == "__main__":
    main()
