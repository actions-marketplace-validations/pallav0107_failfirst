from sympy.physics import units
from sympy.physics.units.systems.si import SI

v1 = units.Quantity('v1')
SI.set_quantity_dimension(v1, units.velocity)
SI.set_quantity_scale_factor(v1, 2 * units.meter / units.second)

a1 = units.Quantity('a1')
SI.set_quantity_dimension(a1, units.acceleration)
SI.set_quantity_scale_factor(a1, -9.8 * units.meter / units.second**2)

t1 = units.Quantity('t1')
SI.set_quantity_dimension(t1, units.time)
SI.set_quantity_scale_factor(t1, 5 * units.second)

expr1 = a1*t1 + v1

# The issue is that _collect_factor_and_dimension raises a ValueError
# because it doesn't recognize that acceleration*time has the same dimension as velocity.
# If fixed, this should not raise an error and should return the correct factor and dimension.

try:
    result = SI._collect_factor_and_dimension(expr1)
    # If we get here without exception, the bug is fixed.
    # We can optionally check the result values if needed, but the main point is no exception.
    # The expected dimension is velocity (or length/time).
    # The expected factor is -9.8*5 + 2 = -49 + 2 = -47 m/s
    assert result[0] == -47, f"Expected factor -47, got {result[0]}"
    assert result[1] == units.velocity, f"Expected dimension velocity, got {result[1]}"
except ValueError as e:
    # If ValueError is raised, the bug is still present
    raise AssertionError(f"Bug still present: {e}")
