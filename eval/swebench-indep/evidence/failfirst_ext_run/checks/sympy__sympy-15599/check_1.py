from sympy import Symbol, Mod

def main():
    # The issue states that Mod(3*i, 2) should reduce to Mod(i, 2)
    # where i is an integer symbol.
    i = Symbol('i', integer=True)
    
    expr = Mod(3*i, 2)
    expected = Mod(i, 2)
    
    # Check if the expression simplifies as expected
    assert expr == expected, f"Expected {expected}, but got {expr}"

if __name__ == "__main__":
    main()
