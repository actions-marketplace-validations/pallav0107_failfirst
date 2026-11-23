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
    )

django.setup()

from django.db import models
from django.db.models import Avg, Sum, Count, Min, Max
from django.db.models.functions import Coalesce

# Define a simple model for testing
class Item(models.Model):
    value = models.IntegerField()
    
    class Meta:
        app_label = 'test_app'

# Create the table
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Item)

# Insert test data
# We want to test DISTINCT behavior.
# Data: 10, 10, 20
# Sum(DISTINCT value) should be 10 + 20 = 30
# Sum(value) should be 10 + 10 + 20 = 40
# Avg(DISTINCT value) should be (10 + 20) / 2 = 15.0
# Avg(value) should be (10 + 10 + 20) / 3 = 13.333...

Item.objects.bulk_create([
    Item(value=10),
    Item(value=10),
    Item(value=20),
])

# Test Sum with distinct
try:
    result_sum_distinct = Item.objects.aggregate(Sum('value', distinct=True))['value__sum']
    result_sum_all = Item.objects.aggregate(Sum('value'))['value__sum']
    
    # Assert that distinct is actually doing something different
    assert result_sum_distinct == 30, f"Sum(DISTINCT) expected 30, got {result_sum_distinct}"
    assert result_sum_all == 40, f"Sum(ALL) expected 40, got {result_sum_all}"
except Exception as e:
    print(f"Error during Sum test: {e}")
    sys.exit(1)

# Test Avg with distinct
try:
    result_avg_distinct = Item.objects.aggregate(Avg('value', distinct=True))['value__avg']
    result_avg_all = Item.objects.aggregate(Avg('value'))['value__avg']
    
    # Assert that distinct is actually doing something different
    # Avg(DISTINCT) of (10, 20) is 15.0
    assert result_avg_distinct == 15.0, f"Avg(DISTINCT) expected 15.0, got {result_avg_distinct}"
    # Avg(ALL) of (10, 10, 20) is 13.333...
    assert abs(result_avg_all - 13.333333333333334) < 0.0001, f"Avg(ALL) expected ~13.33, got {result_avg_all}"
except Exception as e:
    print(f"Error during Avg test: {e}")
    sys.exit(1)

print("All tests passed.")
sys.exit(0)
