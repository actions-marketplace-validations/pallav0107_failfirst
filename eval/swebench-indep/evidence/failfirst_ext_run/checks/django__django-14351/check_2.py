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
from django.db.models import Q, Count

# Define models to reproduce the issue
class ManagementAgent(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class PropertyGroup(models.Model):
    name = models.CharField(max_length=100)
    agents = models.ManyToManyField(ManagementAgent, through='ManagementAgentPropertyGroup')

    class Meta:
        app_label = 'test_app'

class ManagementAgentPropertyGroup(models.Model):
    management_agent = models.ForeignKey(ManagementAgent, on_delete=models.CASCADE)
    property_group = models.ForeignKey(PropertyGroup, on_delete=models.CASCADE)

    class Meta:
        app_label = 'test_app'

class TicketRating(models.Model):
    agent = models.ForeignKey(ManagementAgent, on_delete=models.CASCADE)
    value = models.IntegerField()

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(ManagementAgent)
    schema_editor.create_model(PropertyGroup)
    schema_editor.create_model(ManagementAgentPropertyGroup)
    schema_editor.create_model(TicketRating)

# Create test data
agent1 = ManagementAgent.objects.create(name="Agent 1")
agent2 = ManagementAgent.objects.create(name="Agent 2")

pg1 = PropertyGroup.objects.create(name="PG 1")
pg2 = PropertyGroup.objects.create(name="PG 2")

# Link agent1 to pg1
ManagementAgentPropertyGroup.objects.create(management_agent=agent1, property_group=pg1)
# Link agent2 to pg2
ManagementAgentPropertyGroup.objects.create(management_agent=agent2, property_group=pg2)

# Create some ratings
TicketRating.objects.create(agent=agent1, value=10)
TicketRating.objects.create(agent=agent2, value=20)

# Reproduce the issue
# The issue states that using Q(agent__property_groups__in=qs) causes a ProgrammingError
# because the subquery returns all columns instead of just the ID.

# Get the queryset of property groups for agent1
property_groups_qs = PropertyGroup.objects.filter(managementagentpropertygroup__management_agent=agent1)

# This is the problematic query structure from the issue
queryset = TicketRating.objects.annotate(Count("agent__property_groups"))

try:
    # This should work if the bug is fixed. 
    # If the bug exists, it raises "subquery must return only one column" or similar SQL error.
    result = list(queryset.filter(
        Q(agent__property_groups__in=property_groups_qs) | Q(agent__property_groups__count=0)
    ).distinct())
    
    # Verify the result is correct (should contain agent1's rating but not agent2's)
    # agent1 has property_groups count > 0 and is in the filtered qs
    # agent2 has property_groups count > 0 but is NOT in the filtered qs (linked to pg2, filter is for pg1)
    # So only agent1's ticket should be returned.
    
    assert len(result) == 1, f"Expected 1 result, got {len(result)}"
    assert result[0].agent == agent1, f"Expected agent1, got {result[0].agent}"
    
    print("Test passed: The query executed successfully and returned correct results.")
    sys.exit(0)

except Exception as e:
    print(f"Test failed with exception: {e}")
    sys.exit(1)
