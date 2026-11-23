from sympy import symbols, exp, sinh, Piecewise

def main():
    x, y, z = symbols('x y z', real=True)
    expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
    
    # This should not raise a PolynomialError
    try:
        result = expr.subs({1: 1.0})
        # If we get here, the bug is fixed
        print("Success: subs worked without error")
        exit(0)
    except Exception as e:
        # If an exception is raised, the bug is still present
        print(f"Failure: subs raised {type(e).__name__}: {e}")
        raise AssertionError("The bug is still present: subs raised an unexpected exception") from e

if __name__ == "__main__":
    main()
