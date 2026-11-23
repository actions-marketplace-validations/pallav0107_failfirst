import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        USE_TZ=True,
    )

django.setup()

from django.db import models
from django.db.models.query_utils import RegisterLookupMixin


class CustomLookup(models.Lookup):
    lookup_name = 'custom'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s = %s' % (lhs, rhs), params


class TestField(models.IntegerField):
    pass


def test_unregister_lookup_clears_cache():
    """
    Test that _unregister_lookup clears the lookup cache.
    
    The issue states that RegisterLookupMixin._unregister_lookup() should clear 
    the lookup cache, similar to how register_lookup does it.
    """
    # Get the class that has the lookup registry
    # We'll use a simple model field to test this
    
    # First, register a custom lookup
    TestField.register_lookup(CustomLookup)
    
    # Verify it's registered by checking the lookups dict
    assert 'custom' in TestField.get_lookups(), "Custom lookup should be registered"
    
    # Now unregister it
    TestField._unregister_lookup(CustomLookup)
    
    # The bug is that the cache is not cleared after unregistering.
    # If the cache is not cleared, get_lookups() might still return the old cached value
    # which includes the unregistered lookup.
    
    # Check if the lookup is actually removed from the internal registry
    assert 'custom' not in TestField.get_lookups(), \
        "Custom lookup should be removed from lookups after _unregister_lookup"
    
    # Also verify that the internal _lookups dictionary doesn't contain it
    # The cache mechanism in Django fields uses _lookup_cache or similar
    # Let's check if there's a cache attribute and if it's properly cleared
    
    # In Django 4.1, the lookup cache is stored in _lookup_cache on the field class
    # After unregistering, this cache should be cleared so that next call to get_lookups()
    # rebuilds it without the unregistered lookup
    
    print("Test passed: _unregister_lookup correctly clears the lookup cache")


if __name__ == '__main__':
    try:
        test_unregister_lookup_clears_cache()
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
