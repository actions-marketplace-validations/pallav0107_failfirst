from sympy import Min, Max, oo

# According to the issue, Min() with no arguments should return oo
# and Max() with no arguments should return -oo.

min_result = Min()
max_result = Max()

assert min_result == oo, f"Min() should return oo, but got {min_result}"
assert max_result == -oo, f"Max() should return -oo, but got {max_result}"
