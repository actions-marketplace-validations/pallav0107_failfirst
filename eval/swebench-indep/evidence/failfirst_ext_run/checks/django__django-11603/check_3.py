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
from django.db.models import Avg, Sum, Min, Max, Count
from django.db.models.functions import Now

# Define a simple model for testing
class TestModel(models.Model):
    value = models.IntegerField()

    class Meta:
        app_label = 'test_app'

# Create the table
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Insert test data
TestModel.objects.bulk_create([
    TestModel(value=10),
    TestModel(value=10),
    TestModel(value=20),
])

def check_aggregate_distinct_support(aggregate_class, expected_value_with_distinct, expected_value_without_distinct):
    """
    Check if the aggregate class supports distinct.
    """
    # Without distinct
    result_no_distinct = TestModel.objects.aggregate(result=aggregate_class('value'))['result']
    
    # With distinct
    try:
        result_with_distinct = TestModel.objects.aggregate(result=aggregate_class('value', distinct=True))['result']
    except Exception as e:
        print(f"Error with distinct=True for {aggregate_class.__name__}: {e}")
        return False
    
    # Check if the results are as expected
    if result_with_distinct != expected_value_with_distinct:
        print(f"Expected {expected_value_with_distinct} but got {result_with_distinct} for {aggregate_class.__name__} with distinct=True")
        return False
        
    if result_no_distinct != expected_value_without_distinct:
        print(f"Expected {expected_value_without_distinct} but got {result_no_distinct} for {aggregate_class.__name__} without distinct")
        return False
        
    return True

# Check Avg
assert check_aggregate_distinct_support(Avg, 15.0, 40/3), "Avg does not support distinct correctly"

# Check Sum
assert check_aggregate_distinct_support(Sum, 30, 40), "Sum does not support distinct correctly"

print("All checks passed!")
sys.exit(0)
