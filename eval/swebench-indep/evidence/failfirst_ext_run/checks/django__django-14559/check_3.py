import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django.conf as conf
if not conf.settings.configured:
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
from django.test.utils import setup_test_environment

# Create a simple model for testing
class TestModel(models.Model):
    name = models.CharField(max_length=100)
    value = models.IntegerField(default=0)

    class Meta:
        app_label = 'test_app'

# Create the table
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Create some test data
obj1 = TestModel.objects.create(name='obj1', value=1)
obj2 = TestModel.objects.create(name='obj2', value=2)
obj3 = TestModel.objects.create(name='obj3', value=3)

# Modify objects in memory
obj1.value = 10
obj2.value = 20

# Perform bulk_update
result = TestModel.objects.bulk_update([obj1, obj2], ['value'])

# Check the return value
# The issue states that bulk_update should return the number of rows matched/updated
# If fixed, it should return an integer (number of rows updated)
# If not fixed, it returns None

assert result is not None, "bulk_update() returned None, expected number of rows updated"
assert isinstance(result, int), f"bulk_update() returned {type(result)}, expected int"
assert result == 2, f"bulk_update() returned {result}, expected 2"

print("Check passed: bulk_update() correctly returns the number of rows updated.")
sys.exit(0)
