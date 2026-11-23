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
    root = models.ForeignKey("self", on_delete=models.CASCADE, null=True, related_name='children')
    oneval = models.BigIntegerField(null=True)

class TwoModel(models.Model):
    class Meta:
        app_label = 'test_app'

    id = models.BigAutoField(primary_key=True)
    record = models.ForeignKey(OneModel, on_delete=models.CASCADE)
    twoval = models.BigIntegerField(null=True)

# Create tables
from django.core.management import call_command
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(OneModel)
    schema_editor.create_model(TwoModel)

# Create test data
root_obj = OneModel.objects.create(oneval=1)
child_obj = OneModel.objects.create(root=root_obj, oneval=2)
two_obj = TwoModel.objects.create(record=child_obj, twoval=100)

# Reproduce the issue
qs = TwoModel.objects.filter(record__oneval__in=[1, 2, 3])
qs = qs.order_by("record__root_id")

query_str = str(qs.query)

# The issue states that the buggy query has:
# 1. An unnecessary LEFT OUTER JOIN (T3)
# 2. Incorrect ordering direction (DESC instead of ASC) due to model meta ordering leaking in
# 3. Ordering by T3."id" instead of the direct column

# The fixed/correct behavior should:
# 1. Not have the extra join for a simple foreign key ID lookup if possible, or at least order correctly.
# 2. Order by ASCENDING because order_by("record__root_id") does not specify descending.
# 3. Specifically, the issue highlights that `order_by("record__root_id")` was producing `ORDER BY T3."id" DESC`.
#    The workaround `order_by("record__root__id")` produced `ORDER BY ... "root_id" ASC`.

# Let's check the SQL generated.
# Buggy SQL example from issue:
# ... LEFT OUTER JOIN "orion_onemodel" T3 ON ("orion_onemodel"."root_id" = T3."id") ... ORDER BY T3."id" DESC

# Correct SQL should ideally be simpler and definitely ASC.
# Note: In newer Django versions, accessing _id fields directly might still join if it traverses relations, 
# but the key bug is the inversion of sort order and the unnecessary join complexity caused by self-referential FK handling.

# We assert that the query does NOT contain "DESC" when we asked for ascending (default).
# And we assert that it doesn't use the complex T3 join pattern if a simpler one suffices, 
# but the most critical failure mode described is the wrong sort direction.

# Let's look closely at the generated SQL.
print("Generated SQL:", query_str)

# Check 1: The order should be ASCENDING. The bug caused it to be DESCENDING.
# If "DESC" appears in the ORDER BY clause, it's likely the bug.
# However, we must be careful. Does the correct query ever contain DESC? No, we asked for default (ASC).
assert "DESC" not in query_str.upper().split("ORDER BY")[-1], f"Query incorrectly uses DESC ordering: {query_str}"

# Check 2: The bug involved an extra LEFT OUTER JOIN alias T3 (or similar) for a self-referential FK when ordering by _id.
# The workaround showed that a single INNER JOIN is sufficient.
# While implementation details might vary, the presence of a LEFT OUTER JOIN specifically for the sorting of an ID field 
# which is already available via the first join is the inefficiency/bug.
# In the buggy example: INNER JOIN ... LEFT OUTER JOIN ... ORDER BY T3.id
# In the good example: INNER JOIN ... ORDER BY root_id

# Let's verify that we are ordering by the actual column or a direct reference, not a joined table's PK unnecessarily.
# A robust check for the fix is that the sort order is correct (ASC). 
# The extra join is a performance/correctness issue regarding how the compiler resolves the field.

# Let's strictly check the sorting direction as that is the primary visible error affecting results.
# The issue states: "The query has an unexpected DESCENDING sort... I would expect the order_by() to take precedence."

# If the bug is fixed, "DESC" should not be in the order by clause for this query.
order_by_part = query_str.split("ORDER BY")[-1].strip() if "ORDER BY" in query_str else ""
assert "DESC" not in order_by_part, f"Expected ASC ordering, but got DESC in: {order_by_part}"

# Additionally, let's verify the result set order is actually ascending by ID of the root.
# root_obj.id < child_obj.id (usually). 
# two_obj.record is child_obj. child_obj.root is root_obj.
# So record__root_id is root_obj.id.
# There is only one item, so order doesn't change result list, but the SQL structure matters.

# Let's create another object to ensure sorting works logically if we were to fetch.
root_obj2 = OneModel.objects.create(oneval=3)
child_obj2 = OneModel.objects.create(root=root_obj2, oneval=4)
two_obj2 = TwoModel.objects.create(record=child_obj2, twoval=200)

qs2 = TwoModel.objects.filter(record__oneval__in=[1, 2, 3, 4]).order_by("record__root_id")
results = list(qs2)
# root_obj.id should be less than root_obj2.id (auto increment)
# So two_obj (linked to root_obj) should come before two_obj2 (linked to root_obj2)
if len(results) == 2:
    assert results[0].id < results[1].id, "Results are not sorted in ascending order by record__root_id"

sys.exit(0)
