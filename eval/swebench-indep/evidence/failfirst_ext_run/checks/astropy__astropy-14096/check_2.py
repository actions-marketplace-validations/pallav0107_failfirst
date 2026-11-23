import astropy.coordinates as coord


class custom_coord(coord.SkyCoord):
    @property
    def prop(self):
        return self.random_attr


c = custom_coord('00h42m30s', '+41d12m00s', frame='icrs')

try:
    c.prop
except AttributeError as e:
    # The issue is that the error message says 'prop' doesn't exist,
    # but it should say 'random_attr' doesn't exist.
    # If fixed, the AttributeError should mention 'random_attr'.
    error_message = str(e)
    assert 'random_attr' in error_message, f"Expected 'random_attr' in error message, got: {error_message}"
    assert 'prop' not in error_message or 'random_attr' in error_message, f"Error message is misleading: {error_message}"
    # Exit with 0 if the fix is correct (i.e., random_attr is mentioned)
    exit(0)
except Exception as e:
    # If some other exception occurs, that's unexpected
    raise AssertionError(f"Unexpected exception type: {type(e).__name__}: {e}")

# If no exception was raised, that's also wrong
raise AssertionError("Expected AttributeError was not raised")
