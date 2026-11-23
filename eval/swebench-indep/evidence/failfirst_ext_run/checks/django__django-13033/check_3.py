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

from django.db import models, connection
from django.test.utils import setup_test_environment

# Define models as described in the issue
class OneModel(models.Model):
    class Meta:
        app_label = 'testapp'
        ordering = ("-id",)
    
    id = models.BigAutoField(primary_key=True)
    root = models.ForeignKey("self", on_delete=models.CASCADE, null=True, related_name='children')
    oneval = models.BigIntegerField(null=True)

class TwoModel(models.Model):
    class Meta:
        app_label = 'testapp'
    
    id = models.BigAutoField(primary_key=True)
    record = models.ForeignKey(OneModel, on_delete=models.CASCADE)
    twoval = models.BigIntegerField(null=True)

# Create tables
from django.core.management.color import no_style
from django.db import connection

def create_tables():
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(OneModel)
        schema_editor.create_model(TwoModel)

create_tables()

# Reproduce the issue
# The issue states that order_by("record__root_id") produces an incorrect SQL query
# with an unexpected DESCENDING sort and an unnecessary extra JOIN.
# The expected behavior is that order_by should take precedence over the model's Meta ordering
# and produce a simple ASCENDING sort on the root_id column without extra joins.

qs = TwoModel.objects.filter(record__oneval__in=[1,2,3])
qs = qs.order_by("record__root_id")

query_str = str(qs.query)

# Print for debugging if needed, but we rely on assertions
# print(query_str)

# Check 1: The query should NOT have a descending sort (DESC) on the ordered field.
# The issue reports "ORDER BY T3."id" DESC" which is wrong.
# The correct query should order by root_id ASC.
assert "DESC" not in query_str.upper().split("ORDER BY")[-1], f"Query has unexpected DESC in ORDER BY clause: {query_str}"

# Check 2: The query should NOT have an unnecessary LEFT OUTER JOIN to a third table (T3).
# The issue reports "LEFT OUTER JOIN ... T3".
# The correct query should only have one JOIN (INNER JOIN) to OneModel.
assert "T3" not in query_str, f"Query has unnecessary extra join (T3): {query_str}"

# Check 3: The query should order by the root_id field directly, likely from the first joined table.
# The working example shows: ORDER BY "orion_onemodel"."root_id" ASC
# We check that the order by clause references root_id and is ascending (implicit or explicit ASC).
# Since we asserted no DESC, and default is ASC, this should be fine.
# Let's ensure root_id is in the order by clause.
order_by_part = query_str.split("ORDER BY")[-1].strip() if "ORDER BY" in query_str else ""
assert "root_id" in order_by_part.lower(), f"Order by clause does not reference root_id: {order_by_part}"

print("All checks passed. The bug appears to be fixed.")
sys.exit(0)
