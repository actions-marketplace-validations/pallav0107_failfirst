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

from django.db import models, connection
from django.db.models import Sum, Window, F, Coalesce, Aggregate

# Define a simple model for testing
class TestModel(models.Model):
    date = models.DateField()
    DJR = models.FloatField()

    class Meta:
        app_label = 'test_app'

# Create the table
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Insert some test data
TestModel.objects.bulk_create([
    TestModel(date='2023-01-01', DJR=10.0),
    TestModel(date='2023-01-02', DJR=20.0),
    TestModel(date='2023-01-03', DJR=30.0),
])

# Reproduce the issue
try:
    queryset = TestModel.objects.all()
    
    # Annotate with a window function
    queryset = queryset.annotate(
        cumul_DJR=Coalesce(Window(Sum("DJR"), order_by=F("date").asc()), 0.0)
    )
    
    # Try to aggregate over the annotated window function column
    # This is what fails in the bug report: "aggregate function calls cannot contain window function calls"
    result = queryset.aggregate(
        DJR_total=Sum("DJR"),
        cumul_DJR_total=Sum("cumul_DJR")
    )
    
    # If we get here, the query executed without raising an exception.
    # Let's verify the results make sense.
    # DJR_total should be 10 + 20 + 30 = 60
    # cumul_DJR for each row (ordered by date):
    #   Row 1 (2023-01-01): Sum(DJR) over rows up to current = 10
    #   Row 2 (2023-01-02): Sum(DJR) over rows up to current = 10 + 20 = 30
    #   Row 3 (2023-01-03): Sum(DJR) over rows up to current = 10 + 20 + 30 = 60
    # Sum of cumul_DJR = 10 + 30 + 60 = 100
    
    assert result['DJR_total'] == 60.0, f"Expected DJR_total=60.0, got {result['DJR_total']}"
    assert result['cumul_DJR_total'] == 100.0, f"Expected cumul_DJR_total=100.0, got {result['cumul_DJR_total']}"
    
    print("SUCCESS: The issue is fixed. Aggregation over window functions works correctly.")
    sys.exit(0)

except Exception as e:
    print(f"FAILURE: The issue persists. Error: {e}")
    raise AssertionError(f"The bug is not fixed. Exception raised: {e}")
