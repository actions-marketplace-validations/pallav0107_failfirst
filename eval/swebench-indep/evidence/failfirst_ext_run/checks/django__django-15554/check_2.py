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
from django.db.models import Q, F, FilteredRelation, Case, When, CharField, BooleanField, FloatField, ForeignKey, CASCADE

# Define models for testing
class Zone(models.Model):
    name = CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class MyRelation(models.Model):
    zone = ForeignKey(Zone, on_delete=CASCADE, null=True, blank=True)
    
    class Meta:
        app_label = 'test_app'

class Nested(models.Model):
    myrelation = ForeignKey(MyRelation, on_delete=CASCADE, related_name='nested')
    is_all = BooleanField(default=False)
    price = FloatField(default=0.0)
    zone = ForeignKey(Zone, on_delete=CASCADE, null=True, blank=True)

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
zone1 = Zone.objects.create(name='Zone1')
zone2 = Zone.objects.create(name='Zone2')

rel1 = MyRelation.objects.create(zone=zone1)
rel2 = MyRelation.objects.create(zone=zone2)

# Nested entries for rel1
# One specific to zone1
Nested.objects.create(myrelation=rel1, is_all=False, price=10.0, zone=zone1)
# One "all" entry
Nested.objects.create(myrelation=rel1, is_all=True, price=20.0, zone=None)

# Nested entries for rel2
# No specific zone entry, only "all"
Nested.objects.create(myrelation=rel2, is_all=True, price=30.0, zone=None)

# The query from the issue
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

# Check the generated SQL to ensure both joins are present
sql = str(qs.query)

# Debug print (optional, but helpful if run manually)
# print(sql)

# The issue states that only one join is generated. 
# We expect two LEFT OUTER JOINs with different aliases or conditions.
# Specifically, we look for the presence of both filtered relations in the SQL.
# In Django 4.1+, Fixed in later versions, multiple FilteredRelations on the same relation should result in separate JOINs.

# Let's check if the SQL contains references to both filtered relations.
# The aliases used in alias() become table aliases in the SQL.
# We expect to see 'relation_zone' and 'relation_all' in the SQL string as table aliases.

assert 'relation_zone' in sql, "Missing 'relation_zone' alias in SQL"
assert 'relation_all' in sql, "Missing 'relation_all' alias in SQL"

# Furthermore, let's verify the results are correct.
# rel1 has a zone-specific price (10.0) and an all price (20.0). 
# Since zone matches, price_final should be 10.0.
# rel2 has no zone-specific price, only all price (30.0).
# Since zone doesn't match (or is null in nested vs rel2.zone), price_zone is None, so it falls back to 30.0.

results = list(qs.values('id', 'price_final'))
results_dict = {r['id']: r['price_final'] for r in results}

assert rel1.id in results_dict, "rel1 missing from results"
assert rel2.id in results_dict, "rel2 missing from results"

# For rel1, we expect the zone-specific price (10.0) because it exists
assert abs(results_dict[rel1.id] - 10.0) < 0.001, f"Expected 10.0 for rel1, got {results_dict[rel1.id]}"

# For rel2, we expect the 'all' price (30.0) because no zone-specific exists
assert abs(results_dict[rel2.id] - 30.0) < 0.001, f"Expected 30.0 for rel2, got {results_dict[rel2.id]}"

print("All checks passed. The behavior is correct.")
sys.exit(0)
