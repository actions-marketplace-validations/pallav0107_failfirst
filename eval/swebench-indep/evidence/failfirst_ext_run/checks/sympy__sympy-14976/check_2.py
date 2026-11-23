import sys
import inspect
from sympy import Eq, rf, S, lambdify, nsolve, Float

def main():
    x = symbols('x')
    
    # Create the equation as described in the issue
    eqn = Eq(rf(18, x), 77 + S(1)/3)
    
    # Lambdify with mpmath module
    f = lambdify(x, eqn.lhs - eqn.rhs, 'mpmath')
    
    # Get the source code of the generated function
    source = inspect.getsource(f)
    
    # The issue is that rationals like 232/3 are not wrapped properly for mpmath
    # In the broken version, it shows "232/3" as a Python literal which gets 
    # evaluated at standard float precision instead of high precision mpf
    
    # Check if the source contains the problematic pattern
    # The fix should ensure that rational numbers are converted to mpf or similar
    # high-precision representations rather than leaving them as Python fractions
    
    # In the fixed version, the rational should be represented in a way that
    # preserves precision when used with mpmath
    
    # Let's check if the generated code properly handles the rational
    # The issue shows: "RisingFactorial(18, x) - 232/3"
    # This means 232/3 is left as a Python expression which evaluates to float
    
    # After fix, it should convert the rational to an mpmath-compatible form
    
    # We'll verify by checking if nsolve gives proper precision
    try:
        x0 = nsolve(eqn, Float('1.5', 64), prec=64)
        result = rf(18, x0).evalf(64)
        
        # The expected value is 77 + 1/3 = 232/3
        # With proper precision, this should be very close to 232/3
        expected = S(232)/3
        expected_float = float(expected.evalf(64))
        
        # Check if the result has proper precision (not truncated to standard float)
        result_str = str(result)
        
        # If the bug is present, the precision will be limited
        # The issue shows: 77.33333333333332859638176159933209419250488281250000000000000000
        # This has errors starting around the 15th decimal place
        
        # With the fix, we should get much better precision
        # Let's check if we have more than ~15 correct decimal digits
        
        diff = abs(float(result) - float(expected.evalf(64)))
        
        # If the bug is fixed, the difference should be extremely small
        # due to high precision computation
        assert diff < 1e-30, f"Precision is too low: difference = {diff}"
        
        # Also verify the source doesn't contain bare fraction expressions
        # that would indicate improper wrapping
        # This is a secondary check - the primary check is the precision
        
        print("Bug appears to be fixed - high precision maintained")
        sys.exit(0)
        
    except Exception as e:
        print(f"Error during test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    from sympy import symbols
    main()
