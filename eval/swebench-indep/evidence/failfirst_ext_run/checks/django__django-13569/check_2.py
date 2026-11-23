import os
import sys
import django

# Configure Django settings for an in-memory SQLite database
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

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
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
    )

django.setup()

from django.db import models, connection
from django.db.models import Count

# Define models dynamically
class Thing(models.Model):
    class Meta:
        app_label = 'test_app'

class Related(models.Model):
    thing = models.ForeignKey(Thing, on_delete=models.CASCADE)
    
    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Thing)
    schema_editor.create_model(Related)

# Create test data
t = Thing.objects.create()
rs = [Related.objects.create(thing=t) for _ in range(2)]

# Execute the query described in the issue
qs = Thing.objects.annotate(rc=Count('related')).order_by('?').values('id', 'rc')

# The issue states that order_by('?') breaks aggregation by adding RANDOM() to GROUP BY.
# Expected behavior (fixed): The aggregation should remain intact, returning one row with rc=2.
# Broken behavior: The GROUP BY includes RANDOM(), resulting in multiple rows (one per related object) with rc=1.

results = list(qs)

# Debugging output can be helpful but we rely on assertions for exit code
# print(f"Query: {qs.query}")
# print(f"Results: {results}")

# Assertion: We expect exactly one result because there is only one Thing instance.
# If the bug is present, we might get 2 results (one for each Related instance due to broken grouping).
assert len(results) == 1, f"Expected 1 result, got {len(results)}. Results: {results}"

# Assertion: The count should be 2 because there are 2 Related instances pointing to the single Thing.
assert results[0]['rc'] == 2, f"Expected rc=2, got rc={results[0]['rc']}. Results: {results}"

sys.exit(0)
