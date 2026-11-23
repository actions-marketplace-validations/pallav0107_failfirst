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
RangeTuple = namedtuple('RangeTuple', ['near', 'far'])

# Create some test data
TestModel.objects.create(name='test1', value=5)
TestModel.objects.create(name='test2', value=15)
TestModel.objects.create(name='test3', value=25)

# The issue is that passing a named tuple to __range causes an error in Django 3.0+
# because Query.resolve_lookup_value tries to reconstruct the named tuple from an iterator
# but doesn't unpack it correctly.

try:
    # This should work if the bug is fixed
    range_args = RangeTuple(10, 20)
    queryset = TestModel.objects.filter(value__range=range_args)
    results = list(queryset)
    
    # Verify the results are correct
    assert len(results) == 1
    assert results[0].name == 'test2'
    
    # If we get here, the bug is fixed
    print("Bug is fixed: named tuples work with __range")
    sys.exit(0)
    
except TypeError as e:
    # If we get a TypeError about missing arguments, the bug is still present
    if "missing 1 required positional argument" in str(e):
        print(f"Bug is present: {e}")
        sys.exit(1)
    else:
        # Some other TypeError, re-raise
        raise
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
