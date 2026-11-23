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
        USE_TZ=True,
    )

django.setup()

from django.db import models, connection
from django.db.models import Q, Count

# Define models to reproduce the issue
class ManagementAgent(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class PropertyGroup(models.Model):
    name = models.CharField(max_length=100)
    management_agent = models.ForeignKey(ManagementAgent, on_delete=models.CASCADE, related_name='property_groups')

    class Meta:
        app_label = 'test_app'

class TicketRating(models.Model):
    agent = models.ForeignKey(ManagementAgent, on_delete=models.CASCADE, related_name='ratings')
    score = models.IntegerField()

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(ManagementAgent)
    schema_editor.create_model(PropertyGroup)
    schema_editor.create_model(TicketRating)

# Create test data
agent = ManagementAgent.objects.create(name="Test Agent")
pg1 = PropertyGroup.objects.create(name="Group 1", management_agent=agent)
pg2 = PropertyGroup.objects.create(name="Group 2", management_agent=agent)

TicketRating.objects.create(agent=agent, score=5)
TicketRating.objects.create(agent=agent, score=10)

# Reproduce the issue logic
# The issue states that using Q(agent__property_groups__in=qs) causes a ProgrammingError
# because the subquery returns all columns instead of just the PK.

try:
    # This is the problematic query pattern described in the issue
    # We use a queryset for the __in lookup which should ideally only select the PK
    property_groups_qs = PropertyGroup.objects.filter(management_agent=agent)
    
    # Annotate with count to mimic the user's scenario
    queryset = TicketRating.objects.annotate(pg_count=Count("agent__property_groups"))
    
    # This filter combines an __in lookup with a queryset (problematic) and an annotation check
    # In the broken state, this generates a subquery selecting all columns from PropertyGroup
    # causing "subquery must return only one column" error in SQL databases like PostgreSQL.
    # SQLite is more lenient but we can inspect the generated SQL or rely on the fact that 
    # Django's internal query compilation might fail or produce incorrect SQL structure.
    
    # To strictly test the bug fix which ensures only PK is selected for __in subqueries,
    # we can look at the generated query. However, the most robust way is to see if it executes.
    # Since SQLite allows multiple columns in IN (it just matches the first), we need to be careful.
    # But the issue specifically mentions ProgrammingError which happens on strict DBs.
    
    # Let's try to trigger the specific code path. The fix usually involves ensuring that
    # when a QuerySet is used in an __in lookup, it is trimmed to select only the primary key.
    
    # We will execute the query. If the bug exists, on PostgreSQL it would crash.
    # On SQLite, it might not crash, but we can check the internal query structure if needed.
    # However, the prompt asks to exit 0 if correct (fixed).
    
    # Let's construct the exact Q object combination
    q = Q(agent__property_groups__in=property_groups_qs) | Q(pg_count=0)
    
    filtered_qs = queryset.filter(q).distinct()
    
    # Force evaluation
    list(filtered_qs)
    
    # If we get here without exception, it works on SQLite. 
    # To be sure it's fixed properly (i.e., only PK is selected), we can inspect the query.
    # The bug was that get_default_columns returned all fields.
    
    # Let's check the SQL generated for the subquery part if possible, or rely on execution.
    # Since we can't easily switch to Postgres in this script, we rely on the fact that
    # Django 4.0+ fixes this by ensuring the subquery selects only the PK.
    
    # A more direct check: Access the internal query of the filter clause.
    # This is complex. Let's stick to execution success as the primary indicator for SQLite,
    # but actually, the bug report says it raises ProgrammingError.
    # If the code is fixed, it runs. If not, it crashes on strict DBs.
    # Since we are on SQLite, we might need to verify the column count in the subquery manually.
    
    # Let's try to access the compiled SQL to verify only one column is selected in the subquery.
    # This is hard to do generically. 
    
    # Alternative: The fix ensures that `Query.get_default_columns` behaves correctly.
    # Let's assume execution success is sufficient for SQLite if the logic is correct.
    # However, to be rigorous, let's look at the query structure.
    
    # Actually, there is a known test case for this. The fix ensures that when a queryset
    # is used in an __in lookup, it calls `.values_list('pk', flat=True)` internally or equivalent.
    
    # Let's verify by checking if the query compiles without error.
    print("Query executed successfully.")
    
except Exception as e:
    print(f"Error occurred: {e}")
    sys.exit(1)

# Additional verification: Check if the subquery selects only one column.
# We can do this by examining the query object.
from django.db.models.sql.compiler import SQLCompiler

# Re-build the query to inspect it
queryset = TicketRating.objects.annotate(pg_count=Count("agent__property_groups"))
property_groups_qs = PropertyGroup.objects.filter(management_agent=agent)
q = Q(agent__property_groups__in=property_groups_qs) | Q(pg_count=0)
filtered_qs = queryset.filter(q).distinct()

# Get the compiler
compiler = filtered_qs.query.get_compiler(using='default')
# Generate SQL
sql, params = compiler.as_sql()

# Check if the subquery for property groups selects only ID.
# The subquery looks like: SELECT ... FROM propertygroup WHERE ...
# In the broken version, it selects all columns. In fixed, only ID.

# Find the subquery part. It's usually inside an IN clause.
# "U0"."id" IN (SELECT U1."id", U1."name" ... -> Broken
# "U0"."id" IN (SELECT U1."id" ... -> Fixed

# Simple heuristic: Count occurrences of SELECT in the SQL and check the next few tokens?
# Or better, just trust that if it didn't crash and the fix is standard, it's fine.
# But let's look for "SELECT" followed by multiple columns from the same alias in a subquery context.

# Actually, the most reliable way in a script without PG is to check the `query` attribute of the inner queryset
# if we can access it. But the Q object consumes it.

# Let's rely on the fact that the issue is about a crash. If it doesn't crash, it's likely fixed
# or SQLite is masking it. But Django's test suite covers this.
# To be safe, let's assert that the SQL does NOT contain a subquery selecting multiple columns for the PK lookup.

# Extract subqueries roughly
import re
# Look for pattern SELECT ... FROM ... WHERE ... inside parentheses
subqueries = re.findall(r'\(SELECT\s+(.*?)\s+FROM\s+"test_app_propertygroup"', sql, re.IGNORECASE | re.DOTALL)

if subqueries:
    for sq in subqueries:
        # Check if it selects more than just the ID
        # Expected fixed: "U0"."id"
        # Broken: "U0"."id", "U0"."name", ...
        cols = [c.strip() for c in sq.split(',')]
        # Filter out empty strings
        cols = [c for c in cols if c]
        
        # If there are multiple columns selected from the property group table in the subquery, it's broken.
        # Note: There might be joins, so we need to be careful.
        # The bug report shows: SELECT U0."id", U0."created", ...
        # So if we see multiple columns from U0 (or whatever alias), it's bad.
        
        # Simple check: if the number of columns is > 1, it's likely the bug.
        # In the fixed version, it should be exactly 1 (the PK).
        if len(cols) > 1:
            print(f"Bug detected: Subquery selects multiple columns: {sq}")
            sys.exit(1)

print("Behaviour is correct.")
sys.exit(0)
