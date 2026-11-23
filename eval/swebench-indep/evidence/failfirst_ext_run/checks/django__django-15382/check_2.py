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
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
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
# The issue states that filtering with ~Exists(empty_queryset) removes the WHERE block
# and results in EmptyResultSet or missing WHERE clause.

# Case 1: Filter with ~Exists on an empty queryset AND another condition
empty_qs = MyModel.objects.none()
qs = MyModel.objects.filter(~Exists(empty_qs), name='test')

query_str = str(qs.query)

# Debug output to understand what's happening
print("Query SQL:", query_str)

# The expected behavior after fix:
# The EXISTS subquery on an empty queryset should evaluate to FALSE.
# Therefore, ~EXISTS(FALSE) should be TRUE.
# So the filter ~Exists(empty_qs) should effectively be ignored (or treated as always true),
# and the remaining filter name='test' should remain in the WHERE clause.
# 
# Before the fix, the whole WHERE block might be removed or it becomes EmptyResultSet.

# Check if the query is EmptyResultSet
if hasattr(qs.query, 'is_empty'):
    is_empty_result_set = qs.query.is_empty
else:
    # Fallback: check if the string representation indicates empty result set
    is_empty_result_set = 'EmptyResultSet' in query_str

if is_empty_result_set:
    print("FAIL: Query resulted in EmptyResultSet")
    sys.exit(1)

# Check if the WHERE clause contains the 'name' filter
# The query should still filter by name='test'
if 'name' not in query_str.lower():
    print("FAIL: The WHERE block is missing or does not contain the 'name' filter")
    print("Query:", query_str)
    sys.exit(1)

# Additional check: ensure the query is valid and doesn't crash when executed
try:
    list(qs)
except Exception as e:
    print(f"FAIL: Executing the query raised an exception: {e}")
    sys.exit(1)

print("PASS: The behaviour is correct.")
sys.exit(0)
