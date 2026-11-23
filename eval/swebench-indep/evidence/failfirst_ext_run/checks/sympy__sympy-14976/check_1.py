import sys
import inspect
from sympy import Eq, rf, S, lambdify

def main():
    x = None
    # We need to define the symbol x
    from sympy import symbols
    x = symbols('x')
    
    eqn = Eq(rf(18, x), 77 + S(1)/3)
    f = lambdify(x, eqn.lhs - eqn.rhs, 'mpmath')
    
    source = inspect.getsource(f)
    
    # The issue states that rationals are not wrapped, resulting in code like:
    # RisingFactorial(18, x) - 232/3
    # This is problematic because 232/3 is evaluated as a Python float (or integer division in Py3 which is float)
    # before being passed to mpmath, losing precision.
    # 
    # If fixed, the rational should be wrapped in an mpmath-compatible type, e.g., mpf('...') or similar,
    # or the expression should use mpmath's rational handling if available, but typically lambdify with mpmath
    # should convert SymPy Rationals to mpmath.mpf or similar high-precision representations.
    #
    # Let's check if the source contains a bare fraction like "232/3" which indicates the bug.
    # A correct implementation would likely represent this number as a string literal for mpf, 
    # or use an mpmath function call.
    
    # The specific value is 77 + 1/3 = 232/3.
    # In the buggy version, it appears as "232/3".
    
    if "232/3" in source:
        # Bug is present: the rational was not wrapped/converted properly for mpmath
        print("Bug detected: Rational 232/3 found as bare Python expression in lambdified code.")
        print("Source:")
        print(source)
        sys.exit(1)
    else:
        # Bug is fixed: the rational is likely wrapped in mpf() or similar
        print("Bug appears fixed: Bare rational 232/3 not found in lambdified code.")
        print("Source:")
        print(source)
        sys.exit(0)

if __name__ == "__main__":
    main()
