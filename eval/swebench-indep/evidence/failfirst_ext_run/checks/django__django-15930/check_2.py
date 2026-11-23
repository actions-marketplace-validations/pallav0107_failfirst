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
from django.db.models import Case, When, Q, Value, BooleanField

# Define a simple model for testing
class TestModel(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

# Create the table
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Insert some test data
TestModel.objects.create(name="Test 1")
TestModel.objects.create(name="Test 2")

# Reproduce the issue
try:
    # This should not raise a ProgrammingError
    queryset = TestModel.objects.annotate(
        _a=Case(
            When(~Q(pk__in=[]), then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    ).values("pk", "_a")
    
    results = list(queryset)
    
    # Verify the results
    # Since pk__in=[] is empty, ~Q(pk__in=[]) should match all records
    # So _a should be True for all records
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    for result in results:
        assert result['_a'] is True, f"Expected _a to be True, got {result['_a']}"
        
    print("Test passed: Issue is fixed.")
    sys.exit(0)
    
except Exception as e:
    print(f"Test failed: {e}")
    sys.exit(1)
