from sympy import symbols, exp, sinh, Piecewise

def main():
    x, y, z = symbols('x y z', real=True)
    expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
    
    # The issue reports that this raises PolynomialError: Piecewise generators do not make sense
    # If the bug is fixed, this should execute without error.
    try:
        result = expr.subs({1: 1.0})
    except Exception as e:
        raise AssertionError(f"subs raised an unexpected exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
