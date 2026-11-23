import sys

def main():
    from sympy import Symbol, Contains, Reals, Piecewise
    
    x = Symbol('x')
    
    # Test 1: Check if Contains.as_set() returns a proper Set object
    # The issue states that Contains(x, Reals).as_set() incorrectly returns Contains(x, Reals)
    # It should return a Set (specifically Reals in this case, or a set representation)
    contains_expr = Contains(x, Reals)
    as_set_result = contains_expr.as_set()
    
    # If the bug is present, as_set_result will be a Contains object.
    # If fixed, it should be a Set object (and not Contains).
    # Contains is a Boolean function, not a Set.
    from sympy.sets.sets import Set
    from sympy.logic.boolalg import Boolean
    
    # Check if the result is still a Contains instance (the buggy behavior)
    if isinstance(as_set_result, type(contains_expr)):
        # Bug is present: as_set returned the Contains object itself
        raise AssertionError("Contains.as_set() returned a Contains object instead of a Set")
        
    # Check if the result is actually a Set
    if not isinstance(as_set_result, Set):
        raise AssertionError(f"Contains.as_set() did not return a Set object, got {type(as_set_result)}")
        
    # Test 2: The secondary failure mentioned in the issue
    # Piecewise((6, Contains(x, Reals)), (7, True)) should work without AttributeError
    try:
        p = Piecewise((6, Contains(x, Reals)), (7, True))
    except AttributeError as e:
        if "'Contains' object has no attribute 'as_relational'" in str(e):
            raise AssertionError("Piecewise failed with AttributeError on Contains.as_relational")
        else:
            # Some other attribute error, re-raise
            raise
            
    # If we got here, the behavior is correct
    sys.exit(0)

if __name__ == "__main__":
    main()
