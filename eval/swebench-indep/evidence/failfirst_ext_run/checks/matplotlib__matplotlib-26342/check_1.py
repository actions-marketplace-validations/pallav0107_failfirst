import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Create a simple contour plot
x = np.linspace(-3, 3, 100)
y = np.linspace(-3, 3, 100)
X, Y = np.meshgrid(x, y)
Z = np.sin(X) * np.cos(Y)

fig, ax = plt.subplots()
cs = ax.contour(X, Y, Z)

# Check if ContourSet has the set_paths method
if not hasattr(cs, 'set_paths'):
    raise AssertionError("ContourSet does not have set_paths method")

# Get original paths
original_paths = cs.get_paths()

# Create some dummy transformed paths (just copies for this test)
# In reality, Cartopy would apply a transformation, but here we just verify the API exists and works
transformed_paths = [path.copy() for path in original_paths]

# Try to use set_paths
try:
    cs.set_paths(transformed_paths)
except Exception as e:
    raise AssertionError(f"set_paths raised an exception: {e}")

# Verify that the paths were actually updated
new_paths = cs.get_paths()

# Check that the number of paths is the same
assert len(new_paths) == len(transformed_paths), "Number of paths did not match after set_paths"

# Check that the paths are the ones we set (by comparing vertices)
for i, (new_path, expected_path) in enumerate(zip(new_paths, transformed_paths)):
    # Compare vertices
    assert np.allclose(new_path.vertices, expected_path.vertices), f"Path {i} vertices did not match"
    # Compare codes
    assert np.array_equal(new_path.codes, expected_path.codes), f"Path {i} codes did not match"

plt.close(fig)
print("set_paths method works correctly.")
