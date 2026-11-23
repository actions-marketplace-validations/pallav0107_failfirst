import numpy as np
import matplotlib.pyplot as plt

def check_shared_axis_ticks_after_clear():
    """
    Checks if ax.clear() incorrectly adds extra ticks and un-hides shared-axis tick labels.
    
    In the buggy version (3.4.2), calling ax.clear() on shared axes causes:
    1. Tick labels to appear on inner subplots where they should be hidden.
    2. Extra ticks to appear on top/right spines.
    
    In the correct version (3.4.1 and fixed versions), shared axis properties are preserved.
    """
    fig, axes = plt.subplots(2, 2, sharex=True, sharey=True)
    
    x = np.arange(0.0, 2*np.pi, 0.01)
    y = np.sin(x)
    
    # Clear and plot on each axis
    for ax in axes.flatten():
        ax.clear()
        ax.plot(x, y)
    
    # Check that tick labels are hidden where expected due to sharing
    # In a 2x2 grid with sharex=True and sharey=True:
    # - Bottom row (axes[1,0] and axes[1,1]) should have visible x-tick labels
    # - Top row (axes[0,0] and axes[0,1]) should have HIDDEN x-tick labels
    # - Left column (axes[0,0] and axes[1,0]) should have visible y-tick labels
    # - Right column (axes[0,1] and axes[1,1]) should have HIDDEN y-tick labels
    
    ax_top_left = axes[0, 0]
    ax_top_right = axes[0, 1]
    ax_bottom_left = axes[1, 0]
    ax_bottom_right = axes[1, 1]
    
    # Check x-tick labels visibility for top row (should be hidden/empty)
    top_left_xticklabels = ax_top_left.get_xticklabels()
    top_right_xticklabels = ax_top_right.get_xticklabels()
    
    # Check y-tick labels visibility for right column (should be hidden/empty)
    top_right_yticklabels = ax_top_right.get_yticklabels()
    bottom_right_yticklabels = ax_bottom_right.get_yticklabels()
    
    # The bug manifests as tick labels being visible when they should not be.
    # We check if the labels are effectively hidden by checking their visibility property
    # or if they are empty strings. In shared axes, matplotlib sets label visibility to False.
    
    # For shared axes, the tick labels on non-bottom rows should have visibility=False
    for label in top_left_xticklabels:
        assert not label.get_visible(), f"Top-left x-tick label '{label.get_text()}' should be hidden but is visible"
    
    for label in top_right_xticklabels:
        assert not label.get_visible(), f"Top-right x-tick label '{label.get_text()}' should be hidden but is visible"
        
    for label in top_right_yticklabels:
        assert not label.get_visible(), f"Top-right y-tick label '{label.get_text()}' should be hidden but is visible"
        
    for label in bottom_right_yticklabels:
        assert not label.get_visible(), f"Bottom-right y-tick label '{label.get_text()}' should be hidden but is visible"
    
    # Also check that bottom-left has visible labels (sanity check)
    bottom_left_xticklabels = ax_bottom_left.get_xticklabels()
    bottom_left_yticklabels = ax_bottom_left.get_yticklabels()
    
    # At least some labels should be visible in the bottom-left
    visible_x = any(label.get_visible() for label in bottom_left_xticklabels)
    visible_y = any(label.get_visible() for label in bottom_left_yticklabels)
    
    assert visible_x, "Bottom-left x-tick labels should be visible"
    assert visible_y, "Bottom-left y-tick labels should be visible"
    
    plt.close(fig)
    print("Check passed: Shared axis tick labels are correctly hidden after ax.clear()")

if __name__ == "__main__":
    check_shared_axis_ticks_after_clear()
