from sympy import symbols, exp, sinh, Piecewise

def main():
    x, y, z = symbols('x y z', real=True)
    expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
    
    # This should not raise a PolynomialError
    try:
        result = expr.subs({1: 1.0})
    except Exception as e:
        raise AssertionError(f"subs raised an unexpected exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
