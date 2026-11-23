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

# Force drawing to ensure all artists are created
fig.canvas.draw()

# The bug is that edges at the extremities (the extend triangles) are not drawn.
# When drawedges=True, the colorbar should have edges for all segments, including the extends.
# The edges are stored in cbar.outline or potentially as separate line collections.
# In ColorbarBase with drawedges=True, the edges are typically part of the 'lines' collection 
# or drawn via the outline patch. However, specifically for extended regions, 
# there are specific patches for the min and max extends.

# Let's inspect the children of the axes to find the edge lines/patches.
# The colorbar creates a mesh (pcolormesh or similar) and if drawedges is True, 
# it adds line segments. For extended colorbars, the extends are separate polygons.
# If drawedges is True, those extend polygons should also have an edgecolor set 
# or there should be lines drawn around them.

# A robust way to check this without relying on internal structure too much:
# Check if the extend patches have visible edges.
# The extend patches are usually accessible via cbar.minorticks or similar? No.
# Let's look at cbar.solids (the main color blocks) and cbar.lines (the edges).
# Actually, in ColorbarBase, when drawedges=True, it draws lines using ax.plot or similar.
# But for extends, they are filled polygons. 

# Let's check the properties of the extend patches.
# The ColorbarBase object has attributes like 'extend_lower' and 'extend_upper' patches?
# Looking at matplotlib source, the extends are drawn as PolyCollections or Patches.
# Specifically, cbar._extend_lower and cbar._extend_upper might exist or similar.
# In newer versions, the colorbar uses _add_solids which handles edges.

# Alternative approach: Check the linewidth of the outline or the presence of edge lines.
# The issue states that black lines at extremities do not show up.
# This implies that the edgecolor of the extend patches is 'none' or linewidth is 0.

# Let's try to access the extend patches directly if possible.
# In matplotlib.colorbar.ColorbarBase, the extend regions are handled by 
# creating specific patches. We can iterate through ax.patches or ax.collections.

# The main colorbar solids are in cbar.solids (a PolyCollection).
# The edges are drawn separately if drawedges=True. 
# For standard bins, lines are drawn. For extends, they are patches.
# If drawedges is True, the extend patches should have edgecolor != 'none'.

# Let's find the extend patches. They are usually added to the axes.
# There should be two extra patches for 'both' extend.
patches = [artist for artist in ax.get_children() if isinstance(artist, mpl.patches.Patch)]

# Filter for patches that are likely the extend triangles.
# They are usually small and at the ends.
# A more direct way: The ColorbarBase instance might store references.
# cbar.patch is the background. 
# The extends are often stored in cbar._extend_lower_patch and cbar._extend_upper_patch 
# or similar private attributes depending on version. In 3.5, let's look for them.

# In matplotlib 3.5, ColorbarBase creates extend patches in _draw_all.
# They are stored as self.extend_lower and self.extend_upper (which are Patches).
if hasattr(cbar, 'extend_lower') and cbar.extend_lower is not None:
    lower_edge_color = cbar.extend_lower.get_edgecolor()
    lower_linewidth = cbar.extend_lower.get_linewidth()
    
    # If drawedges is True, the edge should not be 'none' and linewidth > 0
    # Edgecolor 'none' means no edge.
    is_lower_edge_visible = (mpl.colors.to_rgba(lower_edge_color)[3] > 0) and (lower_linewidth > 0)
else:
    # If attribute doesn't exist, assume bug or different implementation
    is_lower_edge_visible = False

if hasattr(cbar, 'extend_upper') and cbar.extend_upper is not None:
    upper_edge_color = cbar.extend_upper.get_edgecolor()
    upper_linewidth = cbar.extend_upper.get_linewidth()
    
    is_upper_edge_visible = (mpl.colors.to_rgba(upper_edge_color)[3] > 0) and (upper_linewidth > 0)
else:
    is_upper_edge_visible = False

print(f"Lower extend edge visible: {is_lower_edge_visible}")
print(f"Upper extend edge visible: {is_upper_edge_visible}")

# The bug is fixed if both edges are visible
assert is_lower_edge_visible, "Lower extend edge is not visible despite drawedges=True"
assert is_upper_edge_visible, "Upper extend edge is not visible despite drawedges=True"

plt.close(fig)
exit(0)
