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
from django.db.models.base import ModelBase

# Define models dynamically to simulate the issue
class CustomModel(models.Model):
    name = models.CharField(max_length=16)

    class Meta:
        app_label = 'test_app'

class ProxyCustomModel(CustomModel):
    class Meta:
        app_label = 'test_app'
        proxy = True

class AnotherModel(models.Model):
    custom = models.ForeignKey(
        ProxyCustomModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(CustomModel)
    schema_editor.create_model(AnotherModel)

# Create test data
custom_obj = ProxyCustomModel.objects.create(name="Test Name")
AnotherModel.objects.create(custom=custom_obj)

# Reproduce the issue: QuerySet.only() after select_related() on proxy models
try:
    # This should not raise ValueError: 'id' is not in list
    objs = list(AnotherModel.objects.select_related("custom").only("custom__name").all())
    
    # Verify that we got the object and the related object is accessible
    assert len(objs) == 1, f"Expected 1 object, got {len(objs)}"
    obj = objs[0]
    
    # Accessing the related field should work
    # Note: Since we used only("custom__name"), accessing other fields might trigger another query
    # but it shouldn't crash during the initial fetch.
    assert obj.custom is not None, "Related object should not be None"
    assert obj.custom.name == "Test Name", f"Expected 'Test Name', got '{obj.custom.name}'"
    
    print("Success: The issue is fixed.")
    sys.exit(0)

except ValueError as e:
    if "'id' is not in list" in str(e):
        print(f"Failure: The issue persists. Error: {e}")
        sys.exit(1)
    else:
        # Re-raise if it's a different ValueError
        raise

except Exception as e:
    print(f"Failure: Unexpected error: {e}")
    sys.exit(1)
