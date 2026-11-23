import sys
from sympy import (
    symbols, Rational, pi, asin, Interval, Contains, Lambda, S,
    imageset, ConditionSet
)

def main():
    x, y, n = symbols('x y n')
    
    # Reproduce the issue steps
    # Step 1: Create the ImageSet
    img_set = imageset(Lambda(n, 2*n*pi + asin(y)), S.Integers)
    
    # Step 2: Create the ConditionSet with the ImageSet as the base set
    # The condition is that y is in [-1, 1]
    cond_set = ConditionSet(x, Contains(y, Interval(-1, 1)), img_set)
    
    # Step 3: Perform subs(y, Rational(1,3)) on the ConditionSet
    substituted = cond_set.subs(y, Rational(1, 3))
    
    # Expected behavior:
    # The substitution should replace y with 1/3 in both the condition and the base set.
    # The condition Contains(y, Interval(-1, 1)) becomes Contains(1/3, Interval(-1, 1)), which is True.
    # The base set imageset(Lambda(n, 2*n*pi + asin(y)), S.Integers) becomes 
    # imageset(Lambda(n, 2*n*pi + asin(1/3)), S.Integers).
    # Since the condition is True, the ConditionSet should simplify to just the base set.
    
    expected_base_set = imageset(Lambda(n, 2*n*pi + asin(Rational(1, 3))), S.Integers)
    
    # Check if the result is equal to the expected ImageSet
    # Note: In SymPy, ConditionSet with a True condition often simplifies to the base set.
    # If it doesn't simplify automatically, we might need to check structure.
    # However, the issue report shows that .subs() gave a weird result where x was confused with y.
    # The correct result should be the ImageSet with y replaced by 1/3.
    
    # Let's check if the substituted result equals the expected ImageSet
    if substituted != expected_base_set:
        # It might be a ConditionSet with True condition, let's check that too
        from sympy import true
        expected_cond_set = ConditionSet(x, true, expected_base_set)
        if substituted != expected_cond_set:
            # Print for debugging if needed, but we will raise AssertionError
            print(f"Substituted result: {substituted}")
            print(f"Expected base set: {expected_base_set}")
            raise AssertionError("subs on ConditionSet with ImageSet did not produce the expected result")
            
    # Additionally, verify that the weird output from the issue is NOT produced
    # The weird output was: {1/3 | 1/3 ∊ {2⋅π⋅n + asin(1/3) | n ∊ ℤ} ∧ (1/3 ∈ {2⋅π⋅n + asin(1/3) | n ∊ ℤ})}
    # This looks like a ConditionSet where the variable x was replaced by 1/3 somehow.
    # We already checked equality, so if it matches expected, this is fine.
    
    sys.exit(0)

if __name__ == "__main__":
    main()
