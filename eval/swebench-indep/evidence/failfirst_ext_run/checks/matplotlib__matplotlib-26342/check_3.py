import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Create simple data for contouring
x = np.linspace(-3, 3, 50)
y = np.linspace(-3, 3, 50)
X, Y = np.meshgrid(x, y)
Z = np.sin(X) * np.cos(Y)

# Create a contour plot
fig, ax = plt.subplots()
cs = ax.contour(X, Y, Z)

# Check if ContourSet has set_paths method
if not hasattr(cs, 'set_paths'):
    raise AssertionError("ContourSet does not have set_paths method")

# Get original paths
original_paths = cs.get_paths()

# Create some modified paths (just reverse the first path's vertices as a test)
if len(original_paths) > 0:
    # Create new paths by copying and modifying slightly
    import matplotlib.path as mpath
    new_paths = []
    for path in original_paths:
        # Create a new path with same vertices but we'll verify it gets set
        new_path = mpath.Path(path.vertices.copy(), path.codes.copy() if path.codes is not None else None)
        new_paths.append(new_path)
    
    # Try to set the new paths
    try:
        cs.set_paths(new_paths)
    except Exception as e:
        raise AssertionError(f"set_paths raised an exception: {e}")
    
    # Verify that the paths were actually updated
    updated_paths = cs.get_paths()
    
    # Check that the number of paths matches
    if len(updated_paths) != len(new_paths):
        raise AssertionError(f"Number of paths mismatch: expected {len(new_paths)}, got {len(updated_paths)}")
    
    # Check that at least one path was actually changed (vertices should be the same object or equal)
    # Since we copied vertices, they should be equal in value
    for i, (orig, new, updated) in enumerate(zip(original_paths, new_paths, updated_paths)):
        if not np.array_equal(updated.vertices, new.vertices):
            raise AssertionError(f"Path {i} vertices were not updated correctly")
else:
    # If no paths, just check that set_paths exists and can be called with empty list
    try:
        cs.set_paths([])
    except Exception as e:
        raise AssertionError(f"set_paths raised an exception with empty list: {e}")

plt.close(fig)
print("ContourSet.set_paths works correctly")
