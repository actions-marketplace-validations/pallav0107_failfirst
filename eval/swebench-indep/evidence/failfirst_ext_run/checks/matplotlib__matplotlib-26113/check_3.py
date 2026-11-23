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
    # Expected: Hexes with count >= 1 are shown.
    fig1, ax1 = plt.subplots()
    hb1 = ax1.hexbin(
        X, Y,
        mincnt=1,
        extent=extent,
        gridsize=gridsize,
        linewidth=0.0,
    )
    
    # Get the counts for each hexagon
    # offsets are the centers of the hexagons that have data
    # array is the value associated with each hexagon (count if C is None)
    counts_no_c = hb1.get_array()
    offsets_no_c = hb1.get_offsets()
    
    # The number of hexagons plotted should correspond to those with count >= 1
    num_hexes_no_c = len(counts_no_c)
    
    # Case 2: mincnt=1, C argument specified
    # Issue report says this behaves like mincnt > 1 (i.e., count >= 2) incorrectly.
    # Fixed behavior should be count >= 1, same as Case 1.
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
    offsets_with_c = hb2.get_offsets()
    
    num_hexes_with_c = len(counts_with_c)
    
    plt.close(fig1)
    plt.close(fig2)
    
    # The core of the bug is that when C is provided, mincnt=1 filters out hexes with exactly 1 point
    # whereas when C is not provided, mincnt=1 keeps them.
    # Therefore, if fixed, the number of hexagons plotted should be identical in both cases.
    
    print(f"Hexagons plotted without C (mincnt=1): {num_hexes_no_c}")
    print(f"Hexagons plotted with C (mincnt=1): {num_hexes_with_c}")
    
    # Assert that the behavior is consistent
    assert num_hexes_no_c == num_hexes_with_c, \
        f"Inconsistent behavior: {num_hexes_no_c} hexes without C vs {num_hexes_with_c} hexes with C"
        
    # Additionally, verify that we are indeed filtering out empty bins (mincnt=1 means count >= 1)
    # In the 'no C' case, get_array returns counts. All should be >= 1.
    assert np.all(counts_no_c >= 1), "Some hexes without C have count < 1"
    
    # In the 'with C' case, get_array returns the reduced C values. 
    # Since Z is all ones, the sum is equal to the count. So all should be >= 1 as well.
    assert np.all(counts_with_c >= 1), "Some hexes with C have reduced value < 1"

if __name__ == '__main__':
    main()
