import numpy as np
import matplotlib.pyplot as plt

def main():
    # Create a 2x2 grid of subplots with shared x and y axes.
    # In a correct implementation, only the bottom row should have visible
    # x-tick labels, and only the left column should have visible y-tick labels.
    fig, axes = plt.subplots(2, 2, sharex=True, sharey=True)

    x = np.arange(0.0, 2 * np.pi, 0.01)
    y = np.sin(x)

    # Clear and plot on each axis to reproduce the bug scenario
    for ax in axes.flatten():
        ax.clear()
        ax.plot(x, y)

    # Force a draw to ensure all properties are updated
    fig.canvas.draw()

    # Check visibility of tick labels based on shared axis logic:
    # - Top row (axes[0, 0] and axes[0, 1]): x-tick labels should be hidden
    # - Bottom row (axes[1, 0] and axes[1, 1]): x-tick labels should be visible
    # - Right column (axes[0, 1] and axes[1, 1]): y-tick labels should be hidden
    # - Left column (axes[0, 0] and axes[1, 0]): y-tick labels should be visible

    # Check top-left axis [0, 0]
    ax_tl = axes[0, 0]
    # X labels should be hidden (shared x, not bottom row)
    for label in ax_tl.get_xticklabels():
        assert not label.get_visible(), "Top-left x-tick label should be hidden"
    # Y labels should be visible (shared y, is left column)
    for label in ax_tl.get_yticklabels():
        assert label.get_visible(), "Top-left y-tick label should be visible"

    # Check top-right axis [0, 1]
    ax_tr = axes[0, 1]
    # X labels should be hidden (shared x, not bottom row)
    for label in ax_tr.get_xticklabels():
        assert not label.get_visible(), "Top-right x-tick label should be hidden"
    # Y labels should be hidden (shared y, not left column)
    for label in ax_tr.get_yticklabels():
        assert not label.get_visible(), "Top-right y-tick label should be hidden"

    # Check bottom-left axis [1, 0]
    ax_bl = axes[1, 0]
    # X labels should be visible (shared x, is bottom row)
    for label in ax_bl.get_xticklabels():
        assert label.get_visible(), "Bottom-left x-tick label should be visible"
    # Y labels should be visible (shared y, is left column)
    for label in ax_bl.get_yticklabels():
        assert label.get_visible(), "Bottom-left y-tick label should be visible"

    # Check bottom-right axis [1, 1]
    ax_br = axes[1, 1]
    # X labels should be visible (shared x, is bottom row)
    for label in ax_br.get_xticklabels():
        assert label.get_visible(), "Bottom-right x-tick label should be visible"
    # Y labels should be hidden (shared y, not left column)
    for label in ax_br.get_yticklabels():
        assert not label.get_visible(), "Bottom-right y-tick label should be hidden"

    plt.close(fig)
    print("All checks passed.")

if __name__ == "__main__":
    main()
