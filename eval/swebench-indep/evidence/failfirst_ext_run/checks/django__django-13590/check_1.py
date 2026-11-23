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
    )

django.setup()

from collections import namedtuple
from django.db import models

# Define a simple model for testing
class TestModel(models.Model):
    value = models.IntegerField()

    class Meta:
        app_label = 'test_app'

# Create the table
from django.core.management.color import no_style
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Define a named tuple type
RangeTuple = namedtuple('RangeTuple', ['near', 'far'])

# Create an instance of the named tuple
range_args = RangeTuple(1, 10)

# Attempt to use the named tuple in a __range lookup
# This should work if the bug is fixed
try:
    # We don't need to actually execute the query, just resolve the lookup
    # to trigger the code path in Query.resolve_lookup_value
    from django.db.models.sql.query import Query
    
    query = Query(TestModel)
    
    # Prepare the lookup
    lookup_name = 'value__range'
    value = range_args
    
    # This internal method is where the bug occurs
    resolved_value = query.resolve_lookup_value(value, None, None)
    
    # If we get here without error, the fix is working
    # Verify that the resolved value is still a tuple-like structure with correct values
    assert isinstance(resolved_value, (list, tuple)), f"Expected list or tuple, got {type(resolved_value)}"
    assert len(resolved_value) == 2, f"Expected length 2, got {len(resolved_value)}"
    assert resolved_value[0] == 1, f"Expected first element 1, got {resolved_value[0]}"
    assert resolved_value[1] == 10, f"Expected second element 10, got {resolved_value[1]}"
    
    print("Bug is fixed: Named tuple arguments to __range work correctly.")
    sys.exit(0)
    
except TypeError as e:
    if "__new__() missing 1 required positional argument" in str(e):
        print(f"Bug is present: {e}")
        sys.exit(1)
    else:
        raise
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
