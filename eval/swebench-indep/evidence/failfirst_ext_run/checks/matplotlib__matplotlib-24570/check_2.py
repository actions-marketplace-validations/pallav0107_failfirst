import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.offsetbox import DrawingArea, HPacker, VPacker, AnchoredOffsetbox, TextArea
from matplotlib.patches import Rectangle

def check_align_behavior():
    """
    Check if the 'align' parameter in HPacker works correctly.
    
    The bug report states that 'top' and 'bottom' are reversed.
    
    In an HPacker (Horizontal Packer), children are arranged horizontally.
    The 'align' parameter controls vertical alignment.
    
    - align='bottom': Children should be aligned at their bottom edges.
      This means the y-coordinate of the bottom of each child should be the same.
    - align='top': Children should be aligned at their top edges.
      This means the y-coordinate of the top of each child should be the same.
    
    We create two DrawingAreas with different heights:
    - da1: height 20
    - da2: height 30
    
    If align='bottom' is working correctly:
    - Both boxes should have the same bottom y-coordinate.
    - Since da2 is taller, its top should be higher than da1's top.
    
    If align='bottom' is broken (reversed to act like 'top'):
    - Both boxes would have the same top y-coordinate.
    - da2's bottom would be lower than da1's bottom.
    """
    
    # Create two drawing areas with different heights
    da1 = DrawingArea(10, 20)  # width=10, height=20
    rect1 = Rectangle((0, 0), 10, 20)
    da1.add_artist(rect1)

    da2 = DrawingArea(10, 30)  # width=10, height=30
    rect2 = Rectangle((0, 0), 10, 30)
    da2.add_artist(rect2)

    # Test with align='bottom'
    pack_bottom = HPacker(children=[da1, da2], pad=0, sep=0, align="bottom")
    
    # We need to render the packer to get the actual positions
    # Create a figure and axis to draw on
    fig, ax = plt.subplots()
    
    # To get the layout information, we need to draw the canvas
    # First, let's add the packer to an AnchoredOffsetbox and then to the axis
    box = AnchoredOffsetbox(child=pack_bottom, loc="center")
    ax.add_artist(box)
    
    # Draw the figure to compute the layout
    fig.canvas.draw()
    
    # Get the bounding boxes of the children after layout
    # The HPacker arranges children horizontally. Let's inspect their positions.
    # We need to access the internal children of the HPacker after it has been laid out.
    
    # Alternative approach: directly check the offset_box layout logic
    # Let's use a more direct method by checking the get_window_extent or similar
    
    # Actually, let's look at how HPacker works internally.
    # After drawing, the children should have their positions set.
    
    # Let's try a different approach: use the _offset_update method or check via rendering
    
    # A simpler way: check the y-positions of the children within the HPacker
    # The HPacker's children are stored in pack_bottom.children
    
    # After drawing, we can check the bounds
    # Let's get the window extent of each child
    
    # Note: The children in HPacker are offset boxes themselves.
    # After the canvas is drawn, their positions should be finalized.
    
    # Let's access the transformed positions
    # The key insight: for align='bottom', the bottoms should align.
    
    # Get the bounding boxes in display coordinates
    # We need to find where da1 and da2 ended up
    
    # Let's traverse the artist hierarchy to find the actual rendered positions
    # This is tricky. Let me try a different approach.
    
    # Instead, let's check by looking at the layout calculation directly.
    # HPacker uses _get_alignment_offsets to determine vertical offsets.
    
    # Let me check if there's a way to get the layout info without full rendering
    
    # Actually, let's just verify by checking relative positions after draw
    renderer = fig.canvas.get_renderer()
    
    # Get the window extents of the two drawing areas
    # They are inside the HPacker, which is inside the AnchoredOffsetbox
    
    # Find da1 and da2 in the artist tree
    def find_artists(artist, target_type):
        """Find all artists of a given type in the hierarchy."""
        results = []
        if isinstance(artist, target_type):
            results.append(artist)
        if hasattr(artist, 'get_children'):
            for child in artist.get_children():
                results.extend(find_artists(child, target_type))
        return results
    
    # This might not work directly because DrawingArea is an OffsetBox, not a standard Artist
    
    # Let me try a more direct approach by examining the HPacker's internal state
    # After draw(), the children should have their offset set
    
    # Check the offset of each child in the HPacker
    # The children list contains the original DrawingArea objects
    # After layout, they should have an offset attribute or similar
    
    # Let's check if the children have been positioned correctly
    # In offsetbox, after layout, the position is stored
    
    # I'll use a heuristic: check the y-position difference
    # For align='bottom', if da1 has height 20 and da2 has height 30,
    # and they are bottom-aligned, then:
    # - bottom_y_da1 == bottom_y_da2
    # - top_y_da2 = bottom_y + 30, top_y_da1 = bottom_y + 20
    # So top_y_da2 > top_y_da1
    
    # If they are incorrectly top-aligned (the bug):
    # - top_y_da1 == top_y_da2
    # - bottom_y_da1 = top_y - 20, bottom_y_da2 = top_y - 30
    # So bottom_y_da2 < bottom_y_da1
    
    # Let's get the window extents
    # The DrawingArea objects should be accessible
    
    # Actually, let me check the implementation approach used in matplotlib tests
    # They often check the bbox after drawing
    
    # Let me try to get the bboxes of the children
    # The HPacker children are da1 and da2
    
    # After drawing, we can get the window extent
    try:
        # Get the patch objects we added, they should reflect the position
        # rect1 and rect2 are inside da1 and da2 respectively
        
        # Get window extent of the rectangles
        bbox1 = rect1.get_window_extent(renderer)
        bbox2 = rect2.get_window_extent(renderer)
        
        # bbox has attributes: x0, y0, x1, y1
        # y0 is the bottom, y1 is the top
        
        bottom1 = bbox1.y0
        bottom2 = bbox2.y0
        top1 = bbox1.y1
        top2 = bbox2.y1
        
        # For correct bottom alignment:
        # bottom1 should equal bottom2 (within floating point tolerance)
        # And since da2 is taller, top2 should be greater than top1
        
        # Allow small tolerance for floating point
        tol = 1e-6
        
        # Check if bottoms are aligned
        bottoms_aligned = abs(bottom1 - bottom2) < tol
        
        # Check if tops are NOT aligned (they shouldn't be for bottom alignment)
        tops_not_aligned = abs(top1 - top2) > tol
        
        # For correct behavior with align='bottom':
        # Bottoms should be aligned, and since da2 is taller, top2 > top1
        assert bottoms_aligned, f"Bottoms not aligned: bottom1={bottom1}, bottom2={bottom2}"
        assert top2 > top1, f"Top of da2 ({top2}) should be greater than top of da1 ({top1}) for bottom alignment"
        
        # Additional check: the difference in tops should equal the difference in heights
        # height diff = 30 - 20 = 10
        # top diff should be approximately 10 (in display coordinates, scaled by dpi)
        # But we can't easily verify the exact pixel value without knowing DPI scaling
        # So we just check the relative ordering
        
    except Exception as e:
        raise AssertionError(f"Failed to check alignment: {e}")
    
    plt.close(fig)

if __name__ == "__main__":
    check_align_behavior()
    print("Alignment check passed!")
