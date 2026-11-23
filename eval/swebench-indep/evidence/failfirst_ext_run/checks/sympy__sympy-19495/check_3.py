import sys
from sympy import symbols, Rational, asin, pi, Contains, Interval, ConditionSet, imageset, Lambda, S

def main():
    x, y, n = symbols('x y n')
    
    # Reproduce the issue: Construct a ConditionSet with an ImageSet base
    img_set = imageset(Lambda(n, 2*n*pi + asin(y)), S.Integers)
    cond_set = ConditionSet(x, Contains(y, Interval(-1, 1)), img_set)
    
    # Perform subs as described in the issue
    result = cond_set.subs(y, Rational(1, 3))
    
    # The expected correct behavior is that the substitution happens inside the ImageSet
    # and the condition is evaluated (True since 1/3 is in [-1, 1]), resulting in just the ImageSet.
    # The bug produced a malformed set where x was replaced by 1/3 incorrectly.
    
    expected_img_set = imageset(Lambda(n, 2*n*pi + asin(Rational(1, 3))), S.Integers)
    
    # Check if the result matches the expected ImageSet
    # Note: In fixed versions, ConditionSet.subs should simplify correctly if the condition becomes True
    # or at least not produce the garbled output shown in the issue.
    
    # Let's check the specific garbled output from the issue to ensure it's NOT present.
    # Issue Out[75]: {1/3 | 1/3 ∊ {2⋅π⋅n + asin(1/3) | n ∊ ℤ} ∧ (1/3 ∈ {2⋅π⋅n + asin(1/3) | n ∊ ℤ})}
    # This looks like a ConditionSet where the variable x was replaced by 1/3.
    
    # A robust check: The result should be equal to the ImageSet with y substituted.
    # If the condition Contains(y, Interval(-1,1)) becomes True, ConditionSet often simplifies to the base set.
    # Even if it doesn't simplify completely, the structure should be valid.
    
    # Let's assert that the result is equal to the expected ImageSet.
    # In SymPy 1.7+, fixes for this issue should make this equality hold.
    
    assert result == expected_img_set, f"Substitution failed. Got: {result}, Expected: {expected_img_set}"
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
