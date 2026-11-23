from sympy import symbols, diophantine

def main():
    m, n = symbols('m n', integer=True)
    
    # The equation is m^4 + n^4 - 2^4 - 3^4 = 0, i.e., m^4 + n^4 = 16 + 81 = 97
    # Integer solutions for m^4 + n^4 = 97:
    # Possible fourth powers: 0, 1, 16, 81, 256...
    # Combinations summing to 97: 16 + 81 = 97. So {|m|, |n|} = {2, 3}.
    # All sign combinations and orderings should be present if permute=True works correctly.
    # Expected solutions (m, n): 
    # (2, 3), (2, -3), (-2, 3), (-2, -3), (3, 2), (3, -2), (-3, 2), (-3, -2)
    
    expected_solutions = {
        (2, 3), (2, -3), (-2, 3), (-2, -3),
        (3, 2), (3, -2), (-3, 2), (-3, -2)
    }
    
    # Test with syms=(m, n)
    sol1 = diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(m, n), permute=True)
    
    # Test with syms=(n, m)
    sol2 = diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(n, m), permute=True)
    
    # Both should return the complete set of solutions
    assert sol1 == expected_solutions, f"First call failed: got {sol1}, expected {expected_solutions}"
    assert sol2 == expected_solutions, f"Second call failed: got {sol2}, expected {expected_solutions}"
    
    # Additionally, they should be equal to each other
    assert sol1 == sol2, f"Solutions differ based on symbol order: {sol1} vs {sol2}"

if __name__ == "__main__":
    main()
