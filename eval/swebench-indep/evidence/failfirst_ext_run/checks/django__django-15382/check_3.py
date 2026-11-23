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
# The issue states: filter on exists-subquery with empty queryset removes whole WHERE block
# qs = MyModel.objects.filter(~models.Exists(MyModel.objects.none()), name='test')
# print(qs.query) -> EmptyResultSet (which means no query is executed, or WHERE is missing)

# Expected behavior after fix: The query should have a WHERE clause that includes the EXISTS subquery condition
# Even if the subquery is empty, the negation of EXISTS (NOT EXISTS) should be true for all rows,
# so the filter should effectively become just `name='test'`. It should NOT result in an EmptyResultSet
# unless there are no rows matching name='test'. But more importantly, the SQL generated should not be "EmptyResultSet"
# which implies the entire query is short-circuited to return nothing.

qs = MyModel.objects.filter(~Exists(MyModel.objects.none()), name='test')

# Get the SQL query string
sql = str(qs.query)

print(f"Generated SQL: {sql}")

# The bug is that the query becomes EmptyResultSet, meaning the WHERE block is removed entirely
# and Django thinks the result will always be empty.
# If fixed, the SQL should contain a WHERE clause (or at least not be an EmptyResultSet).

# Check if the query is an EmptyResultSet
from django.core.exceptions import EmptyResultSet

try:
    # Compiling the query should raise EmptyResultSet if it's optimized to empty
    compiler = qs.query.get_compiler(using='default')
    try:
        sql, params = compiler.as_sql()
        print(f"Compiled SQL: {sql}")
        print(f"Params: {params}")
        
        # If we get here, the query is not an EmptyResultSet
        # The fix should ensure that ~Exists(empty) is treated as True (since NOT EXISTS (empty) is True)
        # So the resulting SQL should effectively be SELECT ... WHERE name='test'
        # It should NOT be empty or missing the WHERE clause for name='test'
        
        # Assert that the SQL contains the condition for name='test'
        assert 'name' in sql.lower() or 'test' in sql.lower(), f"Expected 'name' or 'test' in SQL, got: {sql}"
        
        # If we reach here, the behavior is correct (fixed)
        sys.exit(0)
        
    except EmptyResultSet:
        print("Query compiled to EmptyResultSet - this is the BUG")
        raise AssertionError("The query was incorrectly optimized to EmptyResultSet")

except EmptyResultSet:
    print("Query is EmptyResultSet - this is the BUG")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
