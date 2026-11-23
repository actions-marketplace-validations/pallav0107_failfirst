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
        USE_TZ=True,
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

# Modify objects in memory
obj1.value = 10
obj2.value = 20

# Perform bulk_update
result = TestModel.objects.bulk_update([obj1, obj2], ['value'])

# Check the return value
# The issue states that bulk_update() should return the number of rows matched/updated.
# Before the fix, it returns None. After the fix, it should return an integer (number of rows).
assert result is not None, "bulk_update() returned None, but it should return the number of rows updated."
assert isinstance(result, int), f"bulk_update() should return an int, but got {type(result)}"
assert result == 2, f"bulk_update() should return 2 for 2 updated rows, but got {result}"

print("Check passed: bulk_update() correctly returns the number of rows updated.")
sys.exit(0)
