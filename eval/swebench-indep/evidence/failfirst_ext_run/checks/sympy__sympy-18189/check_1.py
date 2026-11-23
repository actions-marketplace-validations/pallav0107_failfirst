from sympy import symbols
from sympy.solvers.diophantine import diophantine

def main():
    m, n = symbols('m n')
    
    # The equation is n**4 + m**4 - 2**4 - 3**4 = 0
    # Which simplifies to m**4 + n**4 = 16 + 81 = 97
    
    # Case 1: syms=(m, n)
    sol1 = diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(m, n), permute=True)
    
    # Case 2: syms=(n, m)
    sol2 = diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(n, m), permute=True)
    
    # The issue states that sol1 returns all 8 permutations of (+-2, +-3) and (+-3, +-2)
    # while sol2 only returns {(3, 2)}
    # If the bug is fixed, both should return the same complete set of solutions.
    
    # Let's define the expected complete set of integer solutions for m^4 + n^4 = 97
    # Since 2^4 = 16 and 3^4 = 81, and 16+81=97, the base positive solution is (2,3) or (3,2).
    # With signs and order, we expect:
    # (2, 3), (2, -3), (-2, 3), (-2, -3)
    # (3, 2), (3, -2), (-3, 2), (-3, -2)
    
    expected_solutions = {
        (2, 3), (2, -3), (-2, 3), (-2, -3),
        (3, 2), (3, -2), (-3, 2), (-3, -2)
    }
    
    # Check if both results are equal to the expected set
    # Note: diophantine returns sets of tuples. The order in syms determines the order in tuples.
    # For syms=(m,n), tuple is (m_val, n_val)
    # For syms=(n,m), tuple is (n_val, m_val)
    
    # So for syms=(m,n), expected is as above.
    # For syms=(n,m), the tuple is (n, m). 
    # If (m,n) = (2,3) is a solution, then (n,m) = (3,2) is the corresponding tuple.
    # The set of tuples for syms=(n,m) should be:
    expected_solutions_nm = {
        (3, 2), (3, -2), (-3, 2), (-3, -2),
        (2, 3), (2, -3), (-2, 3), (-2, -3)
    }
    # Actually, expected_solutions_nm is the same set as expected_solutions because it contains all permutations.
    
    assert sol1 == expected_solutions, f"Solution with syms=(m,n) is incomplete or incorrect. Got: {sol1}"
    assert sol2 == expected_solutions_nm, f"Solution with syms=(n,m) is incomplete or incorrect. Got: {sol2}"
    
    # Additionally, the core issue is that the results depend on syms order when they shouldn't differ in completeness.
    # While the tuples might be ordered differently based on syms, the set of values represented should be consistent.
    # But since permute=True generates all permutations, both should yield the full set of integer solutions mapped correctly.
    
    print("Test passed: diophantine returns complete results regardless of syms order.")

if __name__ == "__main__":
    main()
