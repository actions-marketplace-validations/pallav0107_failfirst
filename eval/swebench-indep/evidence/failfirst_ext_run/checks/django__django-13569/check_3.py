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

# Execute the problematic query
qs = Thing.objects.annotate(rc=Count('related')).order_by('?').values('id', 'rc')

# Check the generated SQL to ensure RANDOM() is not in GROUP BY
query_str = str(qs.query)

# The issue states that the bug produces:
# GROUP BY "thing"."id", RANDOM()
# The fix should ensure RANDOM() is NOT in the GROUP BY clause.

# We assert that the behavior is FIXED if RANDOM() does NOT appear in the GROUP BY part.
# However, checking the exact SQL string can be fragile across versions.
# A more robust check is the result of the aggregation.

# If the bug exists:
# GROUP BY id, RANDOM() will create separate groups for each random value generated per row (or effectively break the grouping logic intended for aggregation).
# Since there are 2 related objects, a correct COUNT should be 2.
# If broken, it might return 1s or other incorrect counts because the grouping is split by the random function.

result = list(qs)

# There should be exactly one Thing instance
assert len(result) == 1, f"Expected 1 result, got {len(result)}: {result}"

# The count of related objects should be 2
assert result[0]['rc'] == 2, f"Expected rc=2, got rc={result[0]['rc']}: {result}"

# Additionally, let's verify the SQL structure to be sure about the specific issue description
# The issue specifically mentions the GROUP BY clause containing RANDOM().
# In fixed versions, RANDOM() should only be in ORDER BY, not GROUP BY.

# Extract GROUP BY part from query
# This is a simple heuristic check. 
if "GROUP BY" in query_str.upper():
    # Find the group by section
    parts = query_str.upper().split("GROUP BY")
    if len(parts) > 1:
        group_by_section = parts[1].split("ORDER BY")[0] if "ORDER BY" in parts[1] else parts[1]
        # Ensure RANDOM() is not in the GROUP BY section
        assert "RANDOM()" not in group_by_section, f"RANDOM() found in GROUP BY clause: {group_by_section}"

print("Bug is fixed.")
sys.exit(0)
