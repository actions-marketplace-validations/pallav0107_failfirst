import os
import sys
import django

# Configure Django settings
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

# Define models
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

# Create data
t = Thing.objects.create()
rs = [Related.objects.create(thing=t) for _ in range(2)]

# Test the issue
# The issue states that order_by('?') breaks aggregation by adding RANDOM() to GROUP BY.
# Expected behavior after fix: GROUP BY should only contain "thing"."id", not RANDOM().
# Consequently, Count('related') should return 2 for the single Thing instance.

qs = Thing.objects.annotate(rc=Count('related')).order_by('?').values('id', 'rc')

# Check the generated SQL to ensure RANDOM() is not in GROUP BY
query_str = str(qs.query)
# print(query_str) # For debugging if needed

# The bug causes: GROUP BY "thing"."id", RANDOM()
# The fix should cause: GROUP BY "thing"."id"

# We can check the result of the aggregation.
# If GROUP BY includes RANDOM(), each row might be grouped separately or unpredictably,
# but typically with one Thing and 2 Related, if it groups by ID + Random, 
# it might still return one row if Random is evaluated once per group? 
# Actually, the issue report shows it returns two rows with rc=1.
# [{'id': 1, 'rc': 1}, {'id': 1, 'rc': 1}]
# This implies the grouping is broken such that the count is not aggregated correctly across all related objects.

# Let's assert the correct aggregation result.
# There is 1 Thing with 2 Related objects.
# The annotation rc should be 2.
# The values() call should return one dictionary.

results = list(qs)

# Assert that we get exactly one result
assert len(results) == 1, f"Expected 1 result, got {len(results)}: {results}"

# Assert that the count is correct
assert results[0]['rc'] == 2, f"Expected rc=2, got rc={results[0]['rc']}: {results}"

# Additionally, verify the SQL does not contain RANDOM() in the GROUP BY clause
# This is a more direct check of the fix described in the issue.
# The query should look like: SELECT ... GROUP BY "thing"."id" ORDER BY RANDOM()
# It should NOT look like: SELECT ... GROUP BY "thing"."id", RANDOM() ORDER BY RANDOM()

# Simple check: "GROUP BY" part should not contain "RANDOM()"
# Note: The exact SQL format might vary slightly, but the presence of RANDOM() in GROUP BY is the bug.
parts = query_str.split('GROUP BY')
if len(parts) > 1:
    group_by_part = parts[1].split('ORDER BY')[0] if 'ORDER BY' in parts[1] else parts[1]
    assert 'RANDOM()' not in group_by_part.upper(), f"RANDOM() found in GROUP BY clause: {group_by_part}"

sys.exit(0)
