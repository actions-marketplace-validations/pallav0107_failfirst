import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from matplotlib.colors import from_levels_and_colors

# Reproduce the issue setup
my_cmap = mpl.cm.viridis
bounds = np.arange(10)
nb_colors = len(bounds) + 1
colors = my_cmap(np.linspace(100, 255, nb_colors).astype(int))
my_cmap, my_norm = from_levels_and_colors(bounds, colors, extend='both')

fig, ax = plt.subplots(figsize=(5, 1))
cbar = mpl.colorbar.ColorbarBase(ax, cmap=my_cmap, norm=my_norm, orientation='horizontal', drawedges=True)

# The bug is that edges are not drawn at the extremities (the extended triangles).
# When drawedges=True, the colorbar should have outlines around all color regions,
# including the extended min and max triangles.
# 
# We can check this by inspecting the collections in the colorbar axis.
# The colorbar consists of:
# 1. The main pcolormesh or patches for the central colors.
# 2. The extend triangles (if any).
#
# With drawedges=True, the edges should be visible. In matplotlib's implementation,
# drawedges typically adds a LineCollection or sets edgecolors on the patches.
# For ColorbarBase with drawedges=True, it draws lines over the boundaries.
#
# Let's look at the children of the axis. The edges are usually drawn as a LineCollection.
# If the bug exists, the lines covering the extremities (the extend regions) are missing.
#
# A robust way to check is to see if the number of edge segments matches expectations.
# However, a simpler heuristic used in similar checks is to verify that the 'extend'
# patches have edge colors set or that there are line objects covering them.
#
# Let's inspect the specific artists created.
# The colorbar creates a mesh for the main part and PolyCollections for the extends.
# When drawedges=True, it should also add a LineCollection for the edges.
#
# Let's count the number of LineCollections or check their properties.
# Actually, looking at the source code logic for ColorbarBase.drawedges:
# It draws lines at the boundaries of the levels.
# For extend='both', there are extra regions. The lines should cover the boundaries
# of these extended regions too.
#
# We can check if the edge lines exist for the extend regions by checking the 
# extent of the drawn lines.
#
# Alternative approach: Check the edgecolor of the extend patches.
# In some implementations, drawedges might set the edgecolor of the patches themselves.
# But ColorbarBase uses a separate mechanism for edges usually.
#
# Let's look at the artists in the axis.
artists = ax.get_children()
line_collections = [a for a in artists if isinstance(a, mpl.collections.LineCollection)]

# If drawedges=True, there should be at least one LineCollection containing the edges.
assert len(line_collections) > 0, "No LineCollection found, edges might not be drawn at all."

# Now, we need to verify that the lines cover the extremities.
# The colorbar is horizontal. The x-axis represents the data values.
# The bounds are 0 to 9. The extend regions are outside this range visually.
# The lines should span the entire colorbar including the extend triangles.
#
# Let's get the paths from the LineCollection.
lc = line_collections[0]
paths = lc.get_paths()
segments = lc.get_segments()

# If the bug is present, the segments at the very left and very right (the extend tips)
# might be missing. 
# The total number of vertical lines expected:
# For 9 bounds (0..8), there are internal boundaries at 1, 2, ..., 8.
# Plus the boundaries at the start and end of the main region.
# Plus the boundaries for the extend triangles.
#
# Actually, let's look at the visual structure.
# Horizontal colorbar with extend='both':
# <triangle> | color1 | color2 | ... | colorN | <triangle>
# Edges should be at:
# - Left tip of left triangle
# - Boundary between left triangle and first color
# - Boundaries between colors
# - Boundary between last color and right triangle
# - Right tip of right triangle
#
# If drawedges=True, lines are drawn at these boundaries.
# The bug states that edges at extremities do not show up. This likely means
# the outermost boundaries (the tips of the triangles or the outer edges of the triangles)
# are not drawn.
#
# Let's check the x-coordinates of the segments.
all_x = []
for seg in segments:
    for pt in seg:
        all_x.append(pt[0])

if not all_x:
    raise AssertionError("No segments found in LineCollection")

min_x = min(all_x)
max_x = max(all_x)

# The axes limits should give us an idea of the expected range.
xlim = ax.get_xlim()
# The colorbar should span most of the axes.
# The extremities should be near the xlims.
# If the edges at extremities are missing, the min_x and max_x of the lines
# will be significantly inward from the xlims.
#
# Let's calculate the width of the colorbar area.
# The norm is based on bounds 0-9, but with extend, the visual range is larger.
# However, the LineCollection segments should cover the full visual extent.
#
# A more direct check: The number of segments.
# For n colors in the main body (len(bounds)-1 = 8 colors? No, len(bounds)=9, so 8 intervals?
# bounds = np.arange(10) -> 0,1,...,9. len=10.
# from_levels_and_colors with extend='both' creates a cmap with len(bounds)+1 colors?
# The doc says: "If extend is 'min' or 'max', the number of colors is len(levels)+1.
# If extend is 'both', the number of colors is len(levels)+2."
# Here levels=bounds. len(bounds)=10. So 12 colors?
# Wait, the code does:
# nb_colors = len(bounds) + 1 = 11.
# colors = my_cmap(...)
# my_cmap, my_norm = from_levels_and_colors(bounds, colors, extend='both')
# from_levels_and_colors expects len(colors) == len(levels) + (1 if extend in ['min','max'] else 2 if extend=='both' else 0)
# Here len(colors)=11, len(levels)=10. extend='both' expects 12 colors.
# This might cause a warning or error, but let's assume it works or truncates.
# Actually, looking at the reproduction code, it might be slightly incorrect regarding color count,
# but the issue is about drawedges.
#
# Let's rely on the geometric check.
# The xlim of the axis should be close to the min and max of the edge lines if they are drawn correctly.
# If the extremity edges are missing, the lines will stop short.
#
# Get the position of the colorbar axes in figure coordinates to understand the scale.
# But we can compare min_x/max_x of lines to xlim.
# The tolerance should be small.
width = xlim[1] - xlim[0]
margin_left = min_x - xlim[0]
margin_right = xlim[1] - max_x

# If the edges are drawn at the extremities, the lines should reach very close to the limits.
# The "extremities" refer to the outer boundaries of the extend triangles.
# If these are missing, the lines will start/end at the boundary between the extend triangle
# and the first/last regular color.
#
# The distance from the tip to the first internal boundary is roughly the size of one color segment.
# So if the bug is present, margin_left and margin_right will be significant (e.g., > 10% of width).
# If fixed, they should be small (close to 0, within line width tolerance).

# Let's assert that the lines extend to the very edges (within a small tolerance).
tolerance = width * 0.05  # 5% tolerance

assert margin_left < tolerance, f"Left edge is missing or incomplete. Margin: {margin_left}, Tolerance: {tolerance}"
assert margin_right < tolerance, f"Right edge is missing or incomplete. Margin: {margin_right}, Tolerance: {tolerance}"

print("Check passed: Edges are drawn at extremities.")
plt.close(fig)
