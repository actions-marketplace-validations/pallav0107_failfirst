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
from django.db.models import F, Q, FilteredRelation, Case, When

# Define models to reproduce the issue
class Zone(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class MyRelation(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        app_label = 'test_app'

class Nested(models.Model):
    myrelation = models.ForeignKey(MyRelation, on_delete=models.CASCADE, related_name='nested')
    is_all = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        app_label = 'test_app'

# Create tables
from django.core.management.color import no_style
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Zone)
    schema_editor.create_model(MyRelation)
    schema_editor.create_model(Nested)

# Create test data
zone1 = Zone.objects.create(name="Zone 1")
zone2 = Zone.objects.create(name="Zone 2")

rel1 = MyRelation.objects.create(zone=zone1)
rel2 = MyRelation.objects.create(zone=zone2)

# For rel1: has a specific zone entry and an "all" entry
Nested.objects.create(myrelation=rel1, is_all=False, price=10.00, zone=zone1)
Nested.objects.create(myrelation=rel1, is_all=True, price=5.00, zone=None)

# For rel2: only has an "all" entry (no specific zone entry for zone2)
Nested.objects.create(myrelation=rel2, is_all=True, price=7.00, zone=None)

# Reproduce the query from the issue
qs = MyRelation.objects.all().alias(
    relation_zone=FilteredRelation(
        "nested",
        condition=Q(nested__zone=F("zone"))
    ),
    relation_all=FilteredRelation(
        "nested",
        condition=Q(nested__is_all=True)
    ),
).annotate(
    price_zone=F("relation_zone__price"),
    price_final=Case(
        When(
            price_zone__isnull=True,
            then=F("relation_all__price"),
        ),
        default=F("price_zone")
    )
)

# Check the generated SQL to see if both joins are present
sql = str(qs.query)

# The issue states that using multiple FilteredRelation with the same relation 
# generates only a single SQL JOIN and ignores the other.
# We need to verify that BOTH 'relation_zone' and 'relation_all' joins exist in the SQL.
# In SQLite, joins usually look like "JOIN ... AS ..." or similar.
# Let's count how many times we join the nested table with the specific aliases.

# A correct implementation should have two separate joins for the same table 
# with different aliases/conditions.

# Let's check if the SQL contains references to both aliases in JOIN clauses.
# The exact SQL syntax might vary, but we should see both aliases defined.

# Simple check: ensure both aliases appear in the query string in a context that suggests they are joined.
# If the bug exists, one of them will be missing from the JOINs.

# Let's look for the aliases in the SQL.
has_relation_zone = "relation_zone" in sql
has_relation_all = "relation_all" in sql

# Print SQL for debugging if needed (but script should just exit)
# print(sql)

# Assert that both filtered relations are present in the query
assert has_relation_zone, f"Missing 'relation_zone' in SQL query:\n{sql}"
assert has_relation_all, f"Missing 'relation_all' in SQL query:\n{sql}"

# Additionally, let's verify the results are correct
results = list(qs.values('id', 'price_final'))

# rel1 has zone=zone1. It has a nested entry with zone=zone1 (price 10.00) and is_all=True (price 5.00).
# The logic says: use zone level if exists, else fall back to all.
# So for rel1, price_final should be 10.00.

# rel2 has zone=zone2. It has NO nested entry with zone=zone2. It has is_all=True (price 7.00).
# So for rel2, price_final should be 7.00.

expected = {
    rel1.id: 10.00,
    rel2.id: 7.00,
}

for r in results:
    rid = r['id']
    pf = r['price_final']
    # Convert Decimal to float for comparison if needed
    pf_float = float(pf) if pf is not None else None
    expected_val = expected.get(rid)
    assert pf_float == expected_val, f"For relation {rid}, expected price_final {expected_val}, got {pf_float}. SQL:\n{sql}"

print("Check passed: Both FilteredRelations are correctly included in the query.")
sys.exit(0)
