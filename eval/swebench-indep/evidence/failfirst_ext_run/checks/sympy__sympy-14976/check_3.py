import sys
import inspect
from sympy import symbols, Eq, rf, S, lambdify

def main():
    x = symbols('x')
    eqn = Eq(rf(18, x), 77 + S(1)/3)
    
    # Create the lambdified function using mpmath module
    f = lambdify(x, eqn.lhs - eqn.rhs, 'mpmath')
    
    # Get the source code of the generated function
    source = inspect.getsource(f)
    
    # The issue is that rationals like 232/3 are not wrapped properly for mpmath.
    # In the broken version, the source contains "232/3" as a Python rational expression,
    # which gets evaluated using standard float division or Python's Fraction, losing precision.
    # In the fixed version, it should be wrapped in an mpmath-compatible way, e.g., mpf('232')/mpf('3')
    # or similar high-precision representation.
    
    # Check if the raw rational "232/3" appears in the source without proper wrapping.
    # The bug manifests as the literal string "232/3" appearing in the generated code.
    # A fix would ensure that constants are converted to mpmath types (like mpf).
    
    # Let's check if the source contains the problematic pattern.
    # The original issue shows: RisingFactorial(18, x) - 232/3
    # We need to verify that 232/3 is NOT present as a bare Python division.
    
    # However, just checking the string might be fragile. Let's also test the actual behavior.
    # If we evaluate the function with an mpmath number, does it preserve precision?
    
    try:
        import mpmath
        mpmath.mp.dps = 50  # Set high precision
        
        # Evaluate the function at a simple point to see if the constant is high-precision
        # The constant term is 77 + 1/3 = 232/3 ≈ 77.333...
        # If lambdify works correctly with mpmath, the result should use mpmath arithmetic.
        
        # Let's check the source for the tell-tale sign of the bug: bare "232/3"
        if "232/3" in source:
            # This indicates the bug is still present - rational not wrapped
            print("BUG DETECTED: Rational 232/3 is not wrapped for mpmath")
            print("Source:", source)
            sys.exit(1)
        else:
            # The rational has been properly handled
            print("FIX VERIFIED: Rational is properly wrapped for mpmath")
            sys.exit(0)
            
    except Exception as e:
        print(f"Error during check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
