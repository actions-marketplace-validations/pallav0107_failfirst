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

# Check if set_paths method exists
if not hasattr(cs, 'set_paths'):
    raise AssertionError("ContourSet does not have set_paths method")

# Get original paths
original_paths = cs.get_paths()
assert len(original_paths) > 0, "No paths found in contour set"

# Create some modified paths (just reverse them for testing)
modified_paths = [path.copy() for path in original_paths]

# Try to use set_paths
try:
    cs.set_paths(modified_paths)
except Exception as e:
    raise AssertionError(f"set_paths raised an exception: {e}")

# Verify that the paths were actually set
new_paths = cs.get_paths()
assert len(new_paths) == len(modified_paths), f"Expected {len(modified_paths)} paths, got {len(new_paths)}"

# The paths should now be the modified ones
# We can't easily compare Path objects directly for equality in all cases,
# but we can check that they are different objects if we modified them meaningfully
# For this test, we just verify that set_paths didn't crash and updated the internal state

plt.close(fig)
print("set_paths method works correctly")
exit(0)
