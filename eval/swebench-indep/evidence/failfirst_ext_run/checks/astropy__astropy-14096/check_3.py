import astropy.coordinates as coord


class CustomCoord(coord.SkyCoord):
    @property
    def prop(self):
        return self.random_attr


c = CustomCoord('00h42m30s', '+41d12m00s', frame='icrs')

try:
    c.prop
except AttributeError as e:
    # The issue is that the error message says 'prop' doesn't exist,
    # but it should say 'random_attr' doesn't exist.
    # If fixed, the AttributeError should mention 'random_attr'.
    error_message = str(e)
    assert 'random_attr' in error_message, f"Expected 'random_attr' in error message, got: {error_message}"
    assert 'prop' not in error_message or 'random_attr' in error_message, f"Error message is misleading: {error_message}"
    # Exit 0 if the fix is present (i.e., random_attr is mentioned)
    exit(0)
else:
    # If no exception was raised, something is very wrong
    raise AssertionError("Expected AttributeError was not raised")
