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
        USE_TZ=True,
    )

django.setup()

from django.db import models
from django.db.models.query_utils import RegisterLookupMixin

# Define a simple model to test lookups
class TestModel(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'test_app'

# Create a custom lookup for testing
class CustomLookup(models.Lookup):
    lookup_name = 'custom_test'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s = %s' % (lhs, rhs), params

def main():
    # Get the field we want to register/unregister the lookup on
    field = TestModel._meta.get_field('name')
    
    # Register the custom lookup
    field.register_lookup(CustomLookup)
    
    # Verify it is registered by checking the cache or looking it up
    # The lookups are stored in field.get_lookups() which uses a cache
    lookups_before = field.get_lookups()
    assert 'custom_test' in lookups_before, "Custom lookup should be registered"
    
    # Now unregister the lookup
    field._unregister_lookup(CustomLookup)
    
    # Check if the cache was cleared. 
    # If the bug exists, the cache still contains 'custom_test'.
    # If fixed, the cache is cleared and get_lookups() will re-compute without it.
    lookups_after = field.get_lookups()
    
    # This assertion checks if the bug is fixed.
    # If 'custom_test' is still in lookups_after, the cache wasn't cleared, so the bug persists.
    assert 'custom_test' not in lookups_after, "Lookup cache was not cleared after unregistering lookup"

    print("Bug is fixed: Lookup cache is correctly cleared.")
    sys.exit(0)

if __name__ == '__main__':
    try:
        main()
    except AssertionError as e:
        print(f"Bug persists: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during check: {e}")
        sys.exit(1)
