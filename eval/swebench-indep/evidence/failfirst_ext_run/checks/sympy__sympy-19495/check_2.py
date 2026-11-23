import sys
from sympy import (
    symbols, Rational, pi, asin, Interval, Contains, S,
    ConditionSet, ImageSet, Lambda
)

def main():
    x, y, n = symbols('x y n')
    
    # Reproduce the issue scenario from the bug report
    # In [73]: imageset(Lambda(n, 2*n*pi + asin(y)), S.Integers)
    img_set = ImageSet(Lambda(n, 2*n*pi + asin(y)), S.Integers)
    
    # In [74]: ConditionSet(x, Contains(y, Interval(-1,1)), _)
    cond_set = ConditionSet(x, Contains(y, Interval(-1, 1)), img_set)
    
    # In [75]: _.subs(y, Rational(1,3))
    # The bug causes this to produce a strange result where x is confused with y
    substituted = cond_set.subs(y, Rational(1, 3))
    
    # Expected behavior:
    # The condition Contains(y, Interval(-1, 1)) should become Contains(1/3, Interval(-1, 1)) which is True.
    # The base set ImageSet should have y substituted to become ImageSet(Lambda(n, 2*n*pi + asin(1/3)), S.Integers).
    # So the result should be effectively the ImageSet itself (or a ConditionSet with True condition and the substituted ImageSet).
    
    # Let's check what the substituted object looks like.
    # If the bug is present, it might look like:
    # {1/3 | 1/3 ∊ {2⋅π⋅n + asin(1/3) | n ∊ ℤ} ∧ (1/3 ∈ ...)}
    # i.e., the variable x in the ConditionSet was incorrectly replaced by 1/3.
    
    # A correct substitution should yield a set that contains expressions in terms of n, not just the number 1/3.
    # Specifically, the base set of the resulting ConditionSet (if it remains a ConditionSet) or the result itself 
    # should be equivalent to ImageSet(Lambda(n, 2*n*pi + asin(Rational(1,3))), S.Integers).
    
    # Let's verify the structure.
    # If subs works correctly, the condition becomes True because 1/3 is in [-1, 1].
    # Sympy often simplifies ConditionSet(x, True, base_set) to just base_set.
    
    expected_base = ImageSet(Lambda(n, 2*n*pi + asin(Rational(1, 3))), S.Integers)
    
    # Check if the result is equal to the expected ImageSet
    # Note: ConditionSet with True condition might simplify to the base set.
    
    # Let's print for debugging if needed, but we must use asserts.
    # print("Substituted:", substituted)
    # print("Expected:", expected_base)
    
    # The bug manifests as the substituted result being structurally wrong.
    # In the buggy version, substituted.base_set might still contain y, or the variable x is replaced.
    # Let's check if 'y' is still free in the result. It shouldn't be.
    if y in substituted.free_symbols:
        raise AssertionError("y is still in free symbols of substituted result")
        
    # The main check: does the substitution yield the correct set?
    # The correct result is the ImageSet with y replaced by 1/3.
    # We compare against expected_base.
    
    assert substituted == expected_base, f"Substitution failed. Got: {substituted}, Expected: {expected_base}"
    
    # Also check the original example from the issue with solveset_real if possible, 
    # but the core issue is about ConditionSet/ImageSet subs.
    # The issue states that solveset_real case worked fine, so we focus on the failing case.
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
