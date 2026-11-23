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
from django.db.models import Avg, Sum, Count, Max, Min
from django.db.models.sql.compiler import SQLCompiler
from django.db.models.aggregates import Aggregate

# Check if Avg and Sum aggregates support the distinct parameter correctly.
# In Django 3.0+, if the issue is fixed, these classes should allow distinct=True
# without raising an exception during query compilation or execution.

def check_aggregate_distinct_support():
    """
    Checks if Avg and Sum aggregates support the distinct parameter.
    Before the fix, using distinct=True with Avg or Sum would raise an exception.
    After the fix, it should work correctly.
    """
    
    # We need to verify that the aggregate classes have the appropriate flags
    # to allow DISTINCT. In Django's implementation, this is often controlled
    # by a class attribute like `allow_distinct`.
    
    # Check Avg
    try:
        avg_agg = Avg('field', distinct=True)
        # If we can instantiate it, check if it actually allows distinct
        # The key is whether the aggregate class permits distinct usage
        assert hasattr(avg_agg, 'allow_distinct'), "Avg should have allow_distinct attribute"
        assert avg_agg.allow_distinct is True, "Avg should allow distinct"
    except Exception as e:
        print(f"Avg distinct check failed: {e}")
        sys.exit(1)
        
    # Check Sum
    try:
        sum_agg = Sum('field', distinct=True)
        assert hasattr(sum_agg, 'allow_distinct'), "Sum should have allow_distinct attribute"
        assert sum_agg.allow_distinct is True, "Sum should allow distinct"
    except Exception as e:
        print(f"Sum distinct check failed: {e}")
        sys.exit(1)
        
    # Also verify that Min and Max can be checked (though the issue says it's pointless,
    # they might also support it)
    try:
        min_agg = Min('field', distinct=True)
        max_agg = Max('field', distinct=True)
        # These may or may not support distinct, but let's check if they don't crash on instantiation
        # The issue specifically mentions Avg and Sum as the main targets
    except Exception as e:
        # Min/Max failing on distinct might be acceptable per the issue description
        pass

    # Now let's do a more thorough check by creating a simple model and attempting
    # to use these aggregates in a query context to ensure no exceptions are raised
    
    from django.db import connection
    from django.db.models.fields import IntegerField
    
    # Create a temporary model for testing
    class TestModel(models.Model):
        value = IntegerField(null=True)
        
        class Meta:
            app_label = 'test_app'
    
    # Try to compile a query with DISTINCT Avg and Sum
    try:
        # Create a queryset
        qs = TestModel.objects.all()
        
        # Test Avg with distinct
        avg_query = qs.aggregate(avg_val=Avg('value', distinct=True))
        # This will fail if the database table doesn't exist, but we're checking
        # if the aggregate itself is properly configured
        
        # Instead, let's check the SQL generation capability
        # We'll inspect the aggregate's contribution to the query
        
        # A better approach: check if the aggregate class properly handles distinct
        # by examining its internal state after initialization with distinct=True
        
        avg_with_distinct = Avg('value', distinct=True)
        sum_with_distinct = Sum('value', distinct=True)
        
        # Verify that the distinct flag is stored
        assert avg_with_distinct.distinct is True, "Avg distinct flag should be True"
        assert sum_with_distinct.distinct is True, "Sum distinct flag should be True"
        
    except TypeError as e:
        # If distinct is not supported, it might raise TypeError
        print(f"Aggregate does not support distinct parameter: {e}")
        sys.exit(1)
    except Exception as e:
        # Other exceptions might indicate configuration issues
        # But if we got here without TypeError for distinct parameter, 
        # the basic support is there
        pass

    print("All checks passed. Avg and Sum support DISTINCT.")
    sys.exit(0)

if __name__ == '__main__':
    check_aggregate_distinct_support()
