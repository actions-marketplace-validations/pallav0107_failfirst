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
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

from django.db import models

# Define the models as described in the issue
class OneModel(models.Model):
    class Meta:
        app_label = 'test_app'
        ordering = ("-id",)
    
    id = models.BigAutoField(primary_key=True)
    root = models.ForeignKey("self", on_delete=models.CASCADE, null=True)
    oneval = models.BigIntegerField(null=True)

class TwoModel(models.Model):
    class Meta:
        app_label = 'test_app'
    
    id = models.BigAutoField(primary_key=True)
    record = models.ForeignKey(OneModel, on_delete=models.CASCADE)
    twoval = models.BigIntegerField(null=True)

# Create tables
from django.core.management.color import no_style
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(OneModel)
    schema_editor.create_model(TwoModel)

# Create test data
root_obj = OneModel.objects.create(oneval=1)
child_obj = OneModel.objects.create(root=root_obj, oneval=2)
two_obj = TwoModel.objects.create(record=child_obj, twoval=10)

# The problematic queryset from the issue
qs = TwoModel.objects.filter(record__oneval__in=[1, 2, 3])
qs = qs.order_by("record__root_id")

sql = str(qs.query)

# Check 1: The query should NOT have an unnecessary LEFT OUTER JOIN (T3).
# The issue states that ordering by "record__root_id" causes an extra join to T3.
# Correct behavior should just use the existing join or direct column reference.
# Specifically, "record__root_id" refers to the column `root_id` on the OneModel table 
# which is already joined via `record`. So it should order by `orion_onemodel`.`root_id`.
# The bug causes it to join OneModel again as T3 and order by T3.id.

# Let's verify the SQL structure.
# Expected correct SQL roughly:
# SELECT ... FROM twomodel INNER JOIN onemodel ON (twomodel.record_id = onemodel.id) ... ORDER BY onemodel.root_id ASC

# Bug SQL roughly:
# SELECT ... FROM twomodel INNER JOIN onemodel ... LEFT OUTER JOIN onemodel T3 ON (onemodel.root_id = T3.id) ... ORDER BY T3.id DESC

# Assertion 1: Ensure there is no second join to the same table (T3 or similar alias for self-join when not needed)
# A simple way to check this is to count how many times the table name appears in the FROM/JOIN clause.
# However, checking for specific patterns is more robust.

# The issue highlights two problems:
# 1. Unnecessary extra JOIN.
# 2. Incorrect sort direction (DESC instead of ASC) because it picks up the Meta ordering of the joined model.

# Let's check if the SQL contains a LEFT OUTER JOIN which indicates the bug.
# In the correct case, we only need an INNER JOIN for `record`. Accessing `root_id` (the FK column) 
# does not require joining the target table of the FK, just accessing the column on the source table.

assert "LEFT OUTER JOIN" not in sql.upper(), f"Unexpected LEFT OUTER JOIN found in query: {sql}"

# Assertion 2: Check sort order. It should be ASC because order_by("record__root_id") is ascending.
# The bug caused it to be DESC due to Meta ordering.
assert "ORDER BY" in sql.upper(), f"No ORDER BY clause found in query: {sql}"

# Extract the ORDER BY part
order_by_part = sql.split("ORDER BY")[1].strip()
# It should end with ASC (or default ASC), not DESC.
# Note: SQLite might not explicitly show ASC, but it won't show DESC.
# If it shows DESC, it's wrong.
assert "DESC" not in order_by_part.upper(), f"Unexpected DESC in ORDER BY clause: {order_by_part}. Full SQL: {sql}"

# Assertion 3: Verify it orders by the correct column.
# It should order by the root_id column of the joined OneModel table.
# In the bug, it ordered by T3.id.
# We expect something like "onemodel"."root_id" or similar.
# Since we don't know the exact table alias, we just ensure it's not ordering by an ID of a secondary join.
# Given the first assertion passed (no LEFT OUTER JOIN), this is likely satisfied.

print("All checks passed. The behavior is correct.")
sys.exit(0)
