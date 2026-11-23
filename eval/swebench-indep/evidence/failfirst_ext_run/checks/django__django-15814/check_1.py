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
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
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

# Reproduce the issue
try:
    # This should crash in the buggy version with ValueError: 'id' is not in list
    objs = list(AnotherModel.objects.select_related("custom").only("custom__name").all())
    # If we reach here, the bug is fixed
    print("Success: Query executed without error.")
    sys.exit(0)
except ValueError as e:
    if "'id' is not in list" in str(e):
        print(f"Failure: Bug reproduced - {e}")
        sys.exit(1)
    else:
        raise
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
