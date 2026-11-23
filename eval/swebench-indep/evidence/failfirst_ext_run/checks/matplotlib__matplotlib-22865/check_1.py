import matplotlib as mpl
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import from_levels_and_colors

# Reproduce the issue setup
my_cmap = mpl.cm.viridis
bounds = np.arange(10)
nb_colors = len(bounds) + 1
colors = my_cmap(np.linspace(100, 255, nb_colors).astype(int))
my_cmap, my_norm = from_levels_and_colors(bounds, colors, extend='both')

fig, ax = plt.subplots(figsize=(5, 1))
cbar = mpl.colorbar.ColorbarBase(ax, cmap=my_cmap, norm=my_norm, orientation='horizontal', drawedges=True)

# The issue is that edges are not drawn at the extremities (the triangular extend regions)
# when drawedges=True and extend='both'.
# We need to check if the patch objects corresponding to the extend triangles have edge colors set.

# The colorbar consists of several patches:
# - The main color blocks
# - The left extend triangle (if extend in ['min', 'both'])
# - The right extend triangle (if extend in ['max', 'both'])

# Let's inspect the patches in the colorbar axis
patches = [child for child in ax.get_children() if isinstance(child, mpl.patches.Patch)]

# Filter for patches that are likely the extend triangles.
# In a horizontal colorbar with extend='both', there should be two triangular patches
# at the ends. These are usually Polygons or PathPatches.

# A more robust way: check all patches that have an edge color.
# If drawedges=True, all patches should have a non-none edge color and non-zero edge width.

found_extend_patches_with_edges = False

for patch in patches:
    # Check if it's one of the extend regions. 
    # The extend regions are typically the first and last patches added, or can be identified by their geometry.
    # However, a simpler heuristic: if drawedges is True, every colored region should have visible edges.
    
    ec = patch.get_edgecolor()
    lw = patch.get_linewidth()
    
    # Matplotlib default edge color for colorbar patches when drawedges=True is black.
    # If the bug exists, the extend patches might have no edge color or zero linewidth.
    
    # We specifically look for patches that are part of the colorbar mesh.
    # The issue states edges at extremities do not show up.
    
    # Let's check if any patch has a "none" edge color or very small linewidth when it shouldn't.
    # Actually, let's verify that ALL patches have visible edges.
    
    # Convert edge color to see if it's 'none' or transparent
    if hasattr(patch, 'get_facecolor'):
        fc = patch.get_facecolor()
        # Skip if face color is transparent (likely not a colorbar block)
        if fc[-1] == 0:
            continue
            
        # Check edge visibility
        # ec is usually an RGBA tuple
        if isinstance(ec, tuple) and len(ec) >= 4:
            alpha = ec[3]
            is_visible_edge = (lw > 0) and (alpha > 0)
        elif isinstance(ec, str):
            is_visible_edge = (ec.lower() != 'none') and (lw > 0)
        else:
            is_visible_edge = True # Assume visible if unknown format
            
        if not is_visible_edge:
            # This patch has no visible edge, which is bad if drawedges=True
            raise AssertionError(f"Patch with facecolor {fc} has no visible edge (ec={ec}, lw={lw})")

# If we got here without assertion, all patches have visible edges.
plt.close(fig)
exit(0)
