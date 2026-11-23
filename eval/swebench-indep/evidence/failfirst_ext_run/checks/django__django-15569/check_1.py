import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
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
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

from django.db import models
from django.db.models.query_utils import RegisterLookupMixin

# We need a concrete model to test field lookups. 
# Let's create a simple model and use one of its fields.

class TestModel(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'test_app'

# Get the field object
field = TestModel._meta.get_field('name')

# Define a custom lookup to register and then unregister
class CustomLookup(models.Lookup):
    lookup_name = 'custom_test_lookup'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s = %s' % (lhs, rhs), params

# 1. Register the lookup
field.register_lookup(CustomLookup)

# Verify it is registered
assert 'custom_test_lookup' in field.get_lookups(), "Lookup should be registered"

# Accessing get_lookups() populates the cache if it wasn't already.
# The issue states that _unregister_lookup does not clear the cache.
# If the cache is not cleared, subsequent calls to get_lookups() might return the old cached value
# which still contains the unregistered lookup.

# Let's ensure the cache is populated by calling get_lookups()
lookups_before_unregister = field.get_lookups()
assert 'custom_test_lookup' in lookups_before_unregister, "Lookup should be in the cached lookups"

# 2. Unregister the lookup
field._unregister_lookup(CustomLookup)

# 3. Check if the lookup is actually gone from the internal registry
# The _unregister_lookup method removes it from self._lookups.
# However, if the cache (usually stored in __dict__ or a specific cache attribute) is not cleared,
# get_lookups() might return the stale cache.

# In Django's Field class, get_lookups() typically checks for a cached attribute.
# Let's see what get_lookups returns now.
lookups_after_unregister = field.get_lookups()

# The bug is that the cache is not cleared. So if the bug exists, 
# 'custom_test_lookup' will still be in lookups_after_unregister because it was served from cache.
# If the bug is fixed, the cache should be cleared, forcing get_lookups() to rebuild the list,
# which would no longer contain 'custom_test_lookup'.

if 'custom_test_lookup' in lookups_after_unregister:
    # This implies the cache was NOT cleared, so the bug is present.
    print("BUG DETECTED: Lookup still appears in get_lookups() after unregistering.")
    sys.exit(1)
else:
    # This implies the cache WAS cleared (or rebuilt correctly), so the bug is fixed.
    print("FIX VERIFIED: Lookup correctly removed from get_lookups().")
    sys.exit(0)
