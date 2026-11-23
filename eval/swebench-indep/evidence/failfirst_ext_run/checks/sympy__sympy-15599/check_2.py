from sympy import Symbol, Mod

def main():
    # The issue states that Mod(3*i, 2) should reduce to Mod(i, 2) 
    # when i is an integer symbol.
    i = Symbol('i', integer=True)
    
    result = Mod(3*i, 2)
    expected = Mod(i, 2)
    
    # Assert that the simplification has occurred
    assert result == expected, f"Expected {expected}, but got {result}"

if __name__ == "__main__":
    main()
