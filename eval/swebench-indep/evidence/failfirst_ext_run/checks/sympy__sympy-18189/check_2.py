from sympy import symbols, diophantine

def main():
    n, m = symbols('n m', integer=True)
    
    # The equation is n**4 + m**4 - 2**4 - 3**4 = 0
    # Which simplifies to n**4 + m**4 = 16 + 81 = 97
    
    # Test case 1: syms=(m, n)
    sol1 = diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(m, n), permute=True)
    
    # Test case 2: syms=(n, m)
    sol2 = diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(n, m), permute=True)
    
    # The issue reports that sol1 returns 8 solutions while sol2 returns only 1.
    # Both should return the same set of solutions (accounting for variable order).
    
    # Let's determine what the correct solutions are.
    # Integer solutions to a^4 + b^4 = 97.
    # Possible integer fourth powers <= 97: 0^4=0, 1^4=1, 2^4=16, 3^4=81.
    # Combinations:
    # 81 + 16 = 97 -> (3, 2) and permutations/signs.
    # So solutions for (n, m) should include all sign/permutation variants of (3, 2).
    # Since permute=True, we expect all permutations and sign changes.
    
    # Expected solutions for syms=(n, m):
    # n=3, m=2; n=3, m=-2; n=-3, m=2; n=-3, m=-2
    # n=2, m=3; n=2, m=-3; n=-2, m=3; n=-2, m=-3
    # Total 8 solutions.
    
    expected_solutions_nm = {
        (3, 2), (3, -2), (-3, 2), (-3, -2),
        (2, 3), (2, -3), (-2, 3), (-2, -3)
    }
    
    # For syms=(m, n), the tuples are (m, n), so:
    # If (n, m) = (3, 2), then (m, n) = (2, 3)
    # So expected solutions for syms=(m, n) are the same set but with elements swapped?
    # No, the set of values is the same, just the order in the tuple corresponds to the syms order.
    # For syms=(m, n), a solution tuple (a, b) means m=a, n=b.
    # For syms=(n, m), a solution tuple (c, d) means n=c, m=d.
    
    # Let's check if sol2 contains all 8 expected solutions for (n, m).
    assert sol2 == expected_solutions_nm, f"Expected {expected_solutions_nm}, got {sol2}"
    
    # Now check sol1. For syms=(m, n), the expected solutions are:
    # m=3, n=2 -> (3, 2) in (m,n) order? No wait.
    # If n=3, m=2 is a solution, then for syms=(m,n), this corresponds to m=2, n=3, i.e., tuple (2, 3).
    # Let's list them properly.
    # Solutions (n, m): (3,2), (3,-2), (-3,2), (-3,-2), (2,3), (2,-3), (-2,3), (-2,-3)
    # Corresponding (m, n): (2,3), (-2,3), (2,-3), (-2,-3), (3,2), (-3,2), (3,-2), (-3,-2)
    # This is the same set! Because the set contains all combinations.
    
    expected_solutions_mn = expected_solutions_nm  # The set of tuples is identical because it's symmetric
    
    assert sol1 == expected_solutions_mn, f"Expected {expected_solutions_mn}, got {sol1}"
    
    # Also verify that both results are equal
    assert sol1 == sol2, f"Solutions differ based on syms order: {sol1} vs {sol2}"

if __name__ == "__main__":
    main()
