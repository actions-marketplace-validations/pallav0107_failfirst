import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django.conf as conf
conf.settings.configure(
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
from django.db.models import Sum, Window, F, Coalesce

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
TestModel.objects.create(date='2023-01-01', DJR=10.0)
TestModel.objects.create(date='2023-01-02', DJR=20.0)
TestModel.objects.create(date='2023-01-03', DJR=30.0)

# Reproduce the issue
queryset = TestModel.objects.all()
queryset = queryset.annotate(
    cumul_DJR=Coalesce(Window(Sum("DJR"), order_by=F("date").asc()), 0.0)
)

try:
    aggregate = queryset.aggregate(
        DJR_total=Sum("DJR"),
        cumul_DJR_total=Sum("cumul_DJR")
    )
    
    # If we get here, the bug is fixed (no exception raised)
    # Verify the results are reasonable
    assert 'DJR_total' in aggregate
    assert 'cumul_DJR_total' in aggregate
    assert aggregate['DJR_total'] == 60.0
    
    print("SUCCESS: Aggregate over window functions works correctly.")
    sys.exit(0)
    
except Exception as e:
    # If an exception is raised, the bug still exists
    print(f"FAILURE: Exception raised: {type(e).__name__}: {e}")
    sys.exit(1)
