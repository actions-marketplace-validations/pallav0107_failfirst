import os
import sys
import django

# Configure Django settings for an in-memory SQLite database
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
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

from django.db import models

# Define a simple model for testing
class TestModel(models.Model):
    name = models.CharField(max_length=100)
    value = models.IntegerField(default=0)

    class Meta:
        app_label = 'test_app'

# Create the table
from django.core.management.color import no_style
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Create test data
obj1 = TestModel.objects.create(name='obj1', value=1)
obj2 = TestModel.objects.create(name='obj2', value=2)
obj3 = TestModel.objects.create(name='obj3', value=3)

# Modify objects in memory
obj1.value = 10
obj2.value = 20

# Perform bulk_update
result = TestModel.objects.bulk_update([obj1, obj2], ['value'])

# Check the return value
# The issue states that bulk_update should return the number of rows matched/updated.
# If fixed, it should return an integer (specifically 2 in this case).
# If not fixed, it returns None.

assert result is not None, "bulk_update() returned None, expected an integer count of updated rows."
assert isinstance(result, int), f"bulk_update() returned {type(result)}, expected int."
assert result == 2, f"bulk_update() returned {result}, expected 2."

print("Check passed: bulk_update() correctly returns the number of updated rows.")
sys.exit(0)
