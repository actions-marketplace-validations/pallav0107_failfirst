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
    agents = models.ManyToManyField(ManagementAgent, through='AgentPropertyGroup')

    class Meta:
        app_label = 'test_app'

class AgentPropertyGroup(models.Model):
    management_agent = models.ForeignKey(ManagementAgent, on_delete=models.CASCADE)
    property_group = models.ForeignKey(PropertyGroup, on_delete=models.CASCADE)

    class Meta:
        app_label = 'test_app'

class TicketRating(models.Model):
    agent = models.ForeignKey(ManagementAgent, on_delete=models.CASCADE)
    rating = models.IntegerField()

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(ManagementAgent)
    schema_editor.create_model(PropertyGroup)
    schema_editor.create_model(AgentPropertyGroup)
    schema_editor.create_model(TicketRating)

# Create test data
agent = ManagementAgent.objects.create(name="Test Agent")
pg1 = PropertyGroup.objects.create(name="Group 1")
pg2 = PropertyGroup.objects.create(name="Group 2")

# Link agent to pg1
AgentPropertyGroup.objects.create(management_agent=agent, property_group=pg1)

# Create a ticket rating for the agent
TicketRating.objects.create(agent=agent, rating=5)

# Reproduce the issue
# The issue states that using Q(agent__property_groups__in=qs) causes a ProgrammingError
# because the subquery returns all columns instead of just the PK.

# Get the queryset of property groups associated with the agent
property_groups_qs = PropertyGroup.objects.filter(agentpropertygroup__management_agent=agent)

# This is the problematic query structure from the issue
# We annotate with count and then filter with an OR condition involving __in with a queryset
queryset = TicketRating.objects.annotate(pg_count=Count("agent__agentpropertygroup"))

try:
    # This should work if the bug is fixed. 
    # If the bug exists, it will raise django.db.utils.ProgrammingError: subquery must return only one column
    result = list(queryset.filter(
        Q(agent__agentpropertygroup__property_group__in=property_groups_qs) |
        Q(pg_count=0)
    ).distinct())
    
    # If we get here, the query executed without error.
    # Let's verify the result is correct.
    # The agent has 1 property group (pg1), so pg_count is 1.
    # The condition Q(agent__agentpropertygroup__property_group__in=property_groups_qs) should be true.
    assert len(result) == 1, f"Expected 1 result, got {len(result)}"
    assert result[0].id == 1, "Unexpected result ID"
    
    print("Test passed: Query executed successfully and returned expected results.")
    sys.exit(0)

except Exception as e:
    print(f"Test failed with exception: {type(e).__name__}: {e}")
    sys.exit(1)
