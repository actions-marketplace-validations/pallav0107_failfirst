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
        USE_TZ=False,
    )

django.setup()

from django.db import models
from collections import namedtuple

# Define a simple model to test with
class TestModel(models.Model):
    name = models.CharField(max_length=100)
    value = models.IntegerField()

    class Meta:
        app_label = 'test_app'

# Create the table
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Define a named tuple
RangeTuple = namedtuple('RangeTuple', ['start', 'end'])

# The issue is that passing a named tuple to __range causes an error in Django 3.0+
# because Query.resolve_lookup_value tries to reconstruct the tuple from an iterator
# but fails to unpack it correctly for named tuples.

try:
    # This should work if the bug is fixed
    range_tuple = RangeTuple(1, 10)
    
    # We need to trigger the query compilation path that resolves lookup values
    # Creating a queryset with __range filter using a named tuple
    qs = TestModel.objects.filter(value__range=range_tuple)
    
    # Force evaluation of the query to trigger the resolution logic
    # We don't need actual data, just to ensure the query compiles without error
    str(qs.query)
    
    # If we get here, the bug is fixed
    print("Bug is fixed: Named tuple works with __range")
    sys.exit(0)
    
except TypeError as e:
    if "__new__() missing" in str(e) or "missing 1 required positional argument" in str(e):
        print(f"Bug still exists: {e}")
        sys.exit(1)
    else:
        # Some other type error, might be unrelated
        raise
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
