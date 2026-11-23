import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.offsetbox import DrawingArea, HPacker, VPacker, AnchoredOffsetbox, TextArea
from matplotlib.patches import Rectangle

def check_hpacker_align():
    """
    Check if the 'align' parameter in HPacker works correctly.
    
    The bug report states that 'top' and 'bottom' are reversed.
    
    In an HPacker (Horizontal Packer), children are arranged horizontally.
    The 'align' parameter controls vertical alignment.
    
    - align='bottom': Children should be aligned along their bottom edges.
      This means the y-coordinate of the bottom of each child should be the same.
    - align='top': Children should be aligned along their top edges.
      This means the y-coordinate of the top of each child should be the same.
    
    We create two DrawingAreas with different heights:
    da1: height 20
    da2: height 30
    
    If align='bottom', both should have the same bottom y-coordinate.
    Since they are packed horizontally, let's say the baseline is at y=0.
    Then da1 extends from y=0 to y=20, and da2 extends from y=0 to y=30.
    
    If align='top', both should have the same top y-coordinate.
    Let's say the top is at y=H. Then da1 extends from y=H-20 to y=H,
    and da2 extends from y=H-30 to y=H.
    
    We can inspect the positions of the children after drawing.
    """
    
    # Create two drawing areas with different heights
    da1 = DrawingArea(10, 20)
    rect1 = Rectangle((0, 0), 10, 20)
    da1.add_artist(rect1)

    da2 = DrawingArea(10, 30)
    rect2 = Rectangle((0, 0), 10, 30)
    da2.add_artist(rect2)

    # Test with align='bottom'
    pack_bottom = HPacker(children=[da1, da2], pad=0, sep=0, align="bottom")
    
    # We need to render the packer to get actual positions
    fig, ax = plt.subplots()
    
    # To get the layout, we need to draw the figure
    # But first, let's add the packer to the axes
    anchored_box_bottom = AnchoredOffsetbox(child=pack_bottom, loc="center")
    ax.add_artist(anchored_box_bottom)
    
    # Draw the figure to compute layouts
    fig.canvas.draw()
    
    # Get the bounding boxes of the children within the HPacker
    # The HPacker itself has a position. The children are positioned relative to it.
    # Let's access the children directly from the packer
    
    # After drawing, the offset boxes should have their positions set
    # We need to find the actual rendered positions
    
    # Alternative approach: use the get_window_extent or similar
    # But for offset boxes, we can look at the xy offset
    
    # Let's try a more direct approach by examining the layout
    # The HPacker sets the offsets of its children
    
    # Reset for clean test
    plt.close(fig)
    
    # Create fresh objects
    da1_b = DrawingArea(10, 20)
    da2_b = DrawingArea(10, 30)
    
    pack_b = HPacker(children=[da1_b, da2_b], pad=0, sep=0, align="bottom")
    
    fig, ax = plt.subplots(figsize=(5, 5))
    
    # Add to axes via AnchoredOffsetbox to trigger proper layout
    anchored = AnchoredOffsetbox(child=pack_b, loc="lower left", bbox_to_anchor=(0.1, 0.1, 0.8, 0.8), bbox_transform=ax.transAxes)
    ax.add_artist(anchored)
    
    fig.canvas.draw()
    
    # Now check the positions
    # The children of pack_b should have their offsets set
    # pack_b.get_children() returns the children
    
    children = pack_b.get_children()
    assert len(children) == 2, f"Expected 2 children, got {len(children)}"
    
    child1, child2 = children[0], children[1]
    
    # Get the offset of each child (in display coordinates or axes coordinates?)
    # The offset is stored in child1.offsetx, child1.offsety
    
    # For align='bottom', the bottom edges should align.
    # In matplotlib's offset box coordinate system, y increases upward.
    # So if bottoms align, the y-offsets should be such that:
    # offsety_1 == offsety_2 (if we consider the reference point)
    # Actually, let's think about this more carefully.
    
    # The HPacker lays out children horizontally. The align parameter determines
    # how they are vertically positioned relative to each other.
    
    # Let's get the bounding boxes in display coordinates
    bb1 = child1.get_window_extent(fig.canvas.renderer)
    bb2 = child2.get_window_extent(fig.canvas.renderer)
    
    # For align='bottom', the bottom of bb1 and bb2 should be at the same y value
    # bb.ymin is the bottom
    
    print(f"align='bottom': child1 bottom={bb1.ymin:.2f}, child2 bottom={bb2.ymin:.2f}")
    print(f"align='bottom': child1 top={bb1.ymax:.2f}, child2 top={bb2.ymax:.2f}")
    
    # Assert that bottoms are aligned (approximately equal)
    assert abs(bb1.ymin - bb2.ymin) < 1.0, f"For align='bottom', bottoms should align. Got {bb1.ymin} vs {bb2.ymin}"
    
    plt.close(fig)
    
    # Now test align='top'
    da1_t = DrawingArea(10, 20)
    da2_t = DrawingArea(10, 30)
    
    pack_t = HPacker(children=[da1_t, da2_t], pad=0, sep=0, align="top")
    
    fig, ax = plt.subplots(figsize=(5, 5))
    
    anchored = AnchoredOffsetbox(child=pack_t, loc="lower left", bbox_to_anchor=(0.1, 0.1, 0.8, 0.8), bbox_transform=ax.transAxes)
    ax.add_artist(anchored)
    
    fig.canvas.draw()
    
    children = pack_t.get_children()
    child1, child2 = children[0], children[1]
    
    bb1 = child1.get_window_extent(fig.canvas.renderer)
    bb2 = child2.get_window_extent(fig.canvas.renderer)
    
    print(f"align='top': child1 bottom={bb1.ymin:.2f}, child2 bottom={bb2.ymin:.2f}")
    print(f"align='top': child1 top={bb1.ymax:.2f}, child2 top={bb2.ymax:.2f}")
    
    # For align='top', the tops should be aligned
    assert abs(bb1.ymax - bb2.ymax) < 1.0, f"For align='top', tops should align. Got {bb1.ymax} vs {bb2.ymax}"
    
    plt.close(fig)
    
    print("All checks passed!")

if __name__ == "__main__":
    check_hpacker_align()
