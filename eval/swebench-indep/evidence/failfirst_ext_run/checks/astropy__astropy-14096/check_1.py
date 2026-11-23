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
    assert 'random_attr' in str(e), f"Expected 'random_attr' in error message, got: {e}"
    exit(0)
except Exception as e:
    raise AssertionError(f"Unexpected exception type: {type(e).__name__}: {e}")

raise AssertionError("No AttributeError was raised")
