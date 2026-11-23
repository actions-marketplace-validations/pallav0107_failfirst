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
from django.db.models import Exists

# Define a simple model for testing
class MyModel(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

# Create the table
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(MyModel)

# Reproduce the issue
# The issue states that filtering on an exists-subquery with an empty queryset
# removes the whole WHERE block, resulting in EmptyResultSet.
# Expected behavior: The query should still include the other filters (e.g., name='test').

qs = MyModel.objects.filter(~Exists(MyModel.objects.none()), name='test')
query_str = str(qs.query)

# Check if the query is EmptyResultSet
if query_str == 'EmptyResultSet':
    print("FAIL: Query resulted in EmptyResultSet, WHERE block is missing.")
    sys.exit(1)

# Check if the WHERE clause contains the expected filter
# The query should contain the condition for name='test'
if 'name' not in query_str.lower():
    print(f"FAIL: Expected 'name' in query, but got: {query_str}")
    sys.exit(1)

print("PASS: Query correctly includes the WHERE clause.")
sys.exit(0)
