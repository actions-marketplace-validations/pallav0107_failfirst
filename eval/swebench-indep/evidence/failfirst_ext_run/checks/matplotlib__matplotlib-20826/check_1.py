import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def main():
    # Reproduce the issue: shared axes, clear(), then plot.
    fig, axes = plt.subplots(2, 2, sharex=True, sharey=True)
    
    x = np.arange(0.0, 2*np.pi, 0.01)
    y = np.sin(x)
    
    for ax in axes.flatten():
        ax.clear()
        ax.plot(x, y)
    
    # In a 2x2 grid with sharex=True and sharey=True:
    # - Only the bottom row should have visible x tick labels.
    # - Only the left column should have visible y tick labels.
    # - Top-right, top-left (y labels ok), bottom-right (x labels ok) need checking.
    # Specifically:
    # ax[0,0] (top-left): x labels hidden, y labels visible
    # ax[0,1] (top-right): x labels hidden, y labels hidden
    # ax[1,0] (bottom-left): x labels visible, y labels visible
    # ax[1,1] (bottom-right): x labels visible, y labels hidden
    
    ax00 = axes[0, 0]
    ax01 = axes[0, 1]
    ax10 = axes[1, 0]
    ax11 = axes[1, 1]
    
    # Check visibility of tick labels
    # get_xticklabels returns a list of Text objects. We check if any are visible.
    # However, matplotlib might mark them as invisible but they still exist.
    # The proper way is to check the visibility property or whether they are drawn.
    # A robust check is to see if the label's get_visible() is False for those that should be hidden.
    
    # For shared axes, matplotlib sets label visibility to False for non-bottom x-axes
    # and non-left y-axes.
    
    # Check ax01 (top-right): both x and y labels should be hidden (invisible)
    x_labels_01 = ax01.get_xticklabels()
    y_labels_01 = ax01.get_yticklabels()
    
    # If any x label is visible, it's a bug
    x_visible_01 = any(label.get_visible() for label in x_labels_01)
    y_visible_01 = any(label.get_visible() for label in y_labels_01)
    
    assert not x_visible_01, "Top-right subplot has visible x tick labels, but they should be hidden due to sharex."
    assert not y_visible_01, "Top-right subplot has visible y tick labels, but they should be hidden due to sharey."
    
    # Check ax00 (top-left): x labels hidden, y labels visible
    x_labels_00 = ax00.get_xticklabels()
    y_labels_00 = ax00.get_yticklabels()
    
    x_visible_00 = any(label.get_visible() for label in x_labels_00)
    y_visible_00 = any(label.get_visible() for label in y_labels_00)
    
    assert not x_visible_00, "Top-left subplot has visible x tick labels, but they should be hidden due to sharex."
    assert y_visible_00, "Top-left subplot has hidden y tick labels, but they should be visible (left column)."
    
    # Check ax11 (bottom-right): x labels visible, y labels hidden
    x_labels_11 = ax11.get_xticklabels()
    y_labels_11 = ax11.get_yticklabels()
    
    x_visible_11 = any(label.get_visible() for label in x_labels_11)
    y_visible_11 = any(label.get_visible() for label in y_labels_11)
    
    assert x_visible_11, "Bottom-right subplot has hidden x tick labels, but they should be visible (bottom row)."
    assert not y_visible_11, "Bottom-right subplot has visible y tick labels, but they should be hidden due to sharey."
    
    # Check ax10 (bottom-left): both visible
    x_labels_10 = ax10.get_xticklabels()
    y_labels_10 = ax10.get_yticklabels()
    
    x_visible_10 = any(label.get_visible() for label in x_labels_10)
    y_visible_10 = any(label.get_visible() for label in y_labels_10)
    
    assert x_visible_10, "Bottom-left subplot has hidden x tick labels, but they should be visible."
    assert y_visible_10, "Bottom-left subplot has hidden y tick labels, but they should be visible."
    
    plt.close(fig)
    print("All checks passed.")

if __name__ == '__main__':
    main()
