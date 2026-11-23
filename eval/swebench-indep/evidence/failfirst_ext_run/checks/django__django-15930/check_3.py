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
from django.db.models import Q, Case, When, Value, BooleanField

# Define a simple model for testing
class TestModel(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

# Create the table
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Insert a test record
TestModel.objects.create(name="test")

# Reproduce the issue
try:
    # This should not raise a ProgrammingError if the bug is fixed
    result = list(
        TestModel.objects.annotate(
            _a=Case(
                When(~Q(pk__in=[]), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        ).values_list('pk', '_a')
    )
    
    # Check that the annotation worked correctly
    # Since pk__in=[] is empty, ~Q(pk__in=[]) should match all records (True)
    assert len(result) == 1, f"Expected 1 result, got {len(result)}"
    pk, annotated_value = result[0]
    assert annotated_value is True, f"Expected True, got {annotated_value}"
    
    print("Bug is fixed: Case() handles ~Q(pk__in=[]) correctly.")
    sys.exit(0)

except Exception as e:
    print(f"Bug still exists or error occurred: {e}")
    sys.exit(1)
