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
# If the bug is fixed, this should not raise an error.
try:
    result = SI._collect_factor_and_dimension(expr1)
except ValueError:
    # If we get a ValueError, the bug is still present
    raise AssertionError("Bug is still present: ValueError raised when collecting factor and dimension for equivalent dimensions")

# If we reach here, the bug is fixed.
# We can also check that the result is reasonable
# The expression is a1*t1 + v1 = (-9.8 m/s^2 * 5 s) + (2 m/s) = -49 m/s + 2 m/s = -47 m/s
# So the factor should be -47 and the dimension should be velocity
assert result[0] == -47, f"Expected factor -47, got {result[0]}"
assert result[1] == units.velocity, f"Expected dimension velocity, got {result[1]}"

print("Bug is fixed!")
