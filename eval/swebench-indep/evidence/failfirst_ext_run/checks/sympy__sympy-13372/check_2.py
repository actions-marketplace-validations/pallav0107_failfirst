import sys

def main():
    try:
        from sympy import symbols, Max, Mul
    except ImportError:
        print("Failed to import sympy")
        sys.exit(1)

    x, y = symbols('x y')

    # The issue reports that this order works fine
    expr1 = Mul(x, Max(0, y), evaluate=False)
    try:
        result1 = expr1.evalf()
    except Exception as e:
        print(f"Unexpected error on first expression: {e}")
        sys.exit(1)

    # The issue reports that this order raises UnboundLocalError
    expr2 = Mul(Max(0, y), x, evaluate=False)
    try:
        result2 = expr2.evalf()
        # If we get here without exception, the bug is fixed.
        # We just need to ensure it doesn't crash.
    except UnboundLocalError as e:
        print(f"UnboundLocalError still occurs: {e}")
        sys.exit(1)
    except KeyError as e:
        # The traceback shows KeyError happens first, then UnboundLocalError during handling.
        # If the fix is applied, neither should propagate as a crash in this context 
        # if handled properly or if the logic is corrected.
        # However, the specific bug report highlights UnboundLocalError.
        # Let's check if it's the specific UnboundLocalError mentioned.
        print(f"KeyError occurred: {e}")
        sys.exit(1)
    except NotImplementedError:
        # The reporter suggested raising NotImplementedError might be the fix.
        # If it raises NotImplementedError, it means the code path was reached and 
        # handled explicitly rather than crashing with UnboundLocalError.
        # This counts as "fixed" in the sense that it's no longer an unhandled internal error.
        pass
    except Exception as e:
        # Any other unexpected exception
        print(f"Unexpected error: {type(e).__name__}: {e}")
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
