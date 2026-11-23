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

    # Case: mincnt=1 specified, C argument specified
    # The bug report states that this incorrectly requires at least TWO data points
    # instead of one. We expect it to behave like mincnt=1 without C, i.e., 
    # include bins with count >= 1.
    
    fig, ax = plt.subplots()
    hb = ax.hexbin(
        X, Y,
        C=Z,
        reduce_C_function=np.sum,
        mincnt=1,
        extent=extent,
        gridsize=gridsize,
        linewidth=0.0,
        cmap='Blues',
    )
    
    # Get the counts for each hexagon
    counts = hb.get_offsets().shape[0] # This gives number of plotted bins? No.
    # hb.get_array() returns the values (sums in this case).
    # hb.offsets contains the centers of the bins that were plotted.
    
    # To check if bins with exactly 1 point are included, we need to know 
    # if any bin has exactly 1 point in the underlying histogram.
    
    # Let's calculate the expected behavior manually or compare with the no-C case.
    # In the no-C case with mincnt=1, bins with count >= 1 are shown.
    
    fig2, ax2 = plt.subplots()
    hb2 = ax2.hexbin(
        X, Y,
        mincnt=1,
        extent=extent,
        gridsize=gridsize,
        linewidth=0.0,
        cmap='Blues',
    )
    
    # The offsets should be identical if the behavior is consistent.
    # hb.offsets and hb2.offsets contain the coordinates of the plotted bins.
    
    offsets_with_c = hb.get_offsets()
    offsets_without_c = hb2.get_offsets()
    
    # Sort them to compare sets
    # Note: get_offsets returns an array of shape (N, 2)
    
    # Convert to sets of tuples for comparison
    set_with_c = set(map(tuple, offsets_with_c))
    set_without_c = set(map(tuple, offsets_without_c))
    
    # If the bug is present, set_with_c will be a subset of set_without_c 
    # (missing bins with count == 1).
    # If fixed, they should be equal.
    
    assert set_with_c == set_without_c, \
        f"Inconsistent mincnt behavior: bins with C differ from bins without C. " \
        f"Missing bins in C case: {set_without_c - set_with_c}"
        
    plt.close(fig)
    plt.close(fig2)
    
    print("Check passed: mincnt behavior is consistent.")

if __name__ == '__main__':
    main()
