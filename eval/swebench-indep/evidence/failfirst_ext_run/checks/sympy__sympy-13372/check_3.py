import sys

def main():
    from sympy import symbols, Max, Mul
    
    x, y = symbols('x y')
    
    # This case works according to the issue description
    try:
        result1 = Mul(x, Max(0, y), evaluate=False).evalf()
    except Exception as e:
        print(f"Unexpected error in first case: {e}")
        sys.exit(1)
        
    # This case raises UnboundLocalError in the buggy version
    # If fixed, it should either work or raise a more appropriate exception
    # but NOT UnboundLocalError
    try:
        result2 = Mul(Max(0, y), x, evaluate=False).evalf()
        # If we get here without exception, the bug is fixed
        # We just need to ensure no UnboundLocalError was raised
    except UnboundLocalError as e:
        print(f"UnboundLocalError still occurs: {e}")
        sys.exit(1)
    except Exception as e:
        # Other exceptions might be acceptable depending on implementation
        # but UnboundLocalError is definitely a bug
        # Let's check if it's a NotImplementedError which was suggested as fix
        pass
    
    # If we reach here, UnboundLocalError did not occur
    sys.exit(0)

if __name__ == "__main__":
    main()
