import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    # Reproduce the issue scenario
    np.random.seed(42)
    X, Y = np.random.multivariate_normal([0.0, 0.0], [[1.0, 0.1], [0.1, 1.0]], size=250).T
    Z = np.ones_like(X)

    extent = [-3., 3., -3., 3.]
    gridsize = (7, 7)

    # Case 1: mincnt=1, no C argument
    # Expected: plots gridpoints with at least 1 datum (count >= 1)
    fig1, ax1 = plt.subplots()
    hb1 = ax1.hexbin(
        X, Y,
        mincnt=1,
        extent=extent,
        gridsize=gridsize,
        linewidth=0.0,
    )
    # Get the counts for each hexagon that was plotted
    counts_no_c = hb1.get_array()
    
    # Case 2: mincnt=1, C argument specified
    # Expected (if fixed): plots gridpoints with at least 1 datum (count >= 1)
    # Bug behavior: plots gridpoints with at least 2 data points (count > 1)
    fig2, ax2 = plt.subplots()
    hb2 = ax2.hexbin(
        X, Y,
        C=Z,
        reduce_C_function=np.sum,
        mincnt=1,
        extent=extent,
        gridsize=gridsize,
        linewidth=0.0,
    )
    counts_with_c = hb2.get_array()

    plt.close(fig1)
    plt.close(fig2)

    # The issue states that when C is provided and mincnt=1, it behaves like mincnt=2 (strictly greater than).
    # When C is not provided and mincnt=1, it behaves correctly (greater than or equal to).
    
    # We need to verify that the set of hexagons plotted is the same in both cases.
    # If the bug exists, counts_with_c will have fewer elements or different values because 
    # it requires count > 1 instead of count >= 1.
    
    # Since Z is all ones, reduce_C_function=np.sum is equivalent to counting the number of points.
    # So counts_no_c and counts_with_c should be identical if the behavior is consistent.
    
    # Check if the arrays are equal. 
    # Note: get_array() returns the values for the collected patches. 
    # If the number of patches differs, the shapes will differ.
    
    assert counts_no_c.shape == counts_with_c.shape, \
        f"Shape mismatch: no C shape {counts_no_c.shape} vs with C shape {counts_with_c.shape}. " \
        "This indicates inconsistent filtering of hexagons based on C parameter."
    
    assert np.allclose(counts_no_c, counts_with_c), \
        "Values mismatch between hexbins with and without C parameter when mincnt=1."

    print("Check passed: mincnt behavior is consistent.")

if __name__ == '__main__':
    main()
