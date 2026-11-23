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
            'django.contrib.postgres', # Required for ArrayField
        ],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.management import call_command
from django.db.migrations.writer import MigrationWriter
from io import StringIO

# Define the model structure as described in the issue
class Profile(models.Model):
    class Capability(models.TextChoices):
        BASIC = ("BASIC", "Basic")
        PROFESSIONAL = ("PROFESSIONAL", "Professional")

        @classmethod
        def default(cls) -> list:
            return [cls.BASIC]

    # We don't need to actually create the table, just inspect the field deconstruction
    capabilities = ArrayField(
        models.CharField(choices=Capability.choices, max_length=30, blank=True),
        null=True,
        default=Capability.default
    )

    class Meta:
        app_label = 'test_app'

def check_migration_serialization():
    """
    Check if the default value (a classmethod from a nested class) 
    is serialized correctly in migrations.
    
    The issue states that it serializes to `appname.models.Capability.default`
    instead of `appname.models.Profile.Capability.default`.
    """
    field = Profile._meta.get_field('capabilities')
    
    # Deconstruct the field to get the arguments that would be written to migration
    name, path, args, kwargs = field.deconstruct()
    
    # The 'default' should be in kwargs
    assert 'default' in kwargs, "Default value missing from field kwargs"
    
    default_value = kwargs['default']
    
    # Serialize the default value using MigrationWriter to see how it appears in code
    # This mimics what happens during makemigrations
    writer = MigrationWriter({})
    
    # We need to serialize the specific value
    from django.db.migrations.serializer import serializer_factory
    
    try:
        serializer = serializer_factory(default_value)
        serialized_string, imports = serializer.serialize()
    except Exception as e:
        print(f"Serialization failed: {e}")
        sys.exit(1)

    # The correct serialization for a method defined in a nested class
    # inside a model in app 'test_app' should reference the full path.
    # Since Profile is defined in __main__ or this script, the module name might vary,
    # but the key is whether it includes the parent class 'Profile'.
    
    # In a real app 'myapp', it should be 'myapp.models.Profile.Capability.default'.
    # In this script, the module is likely '__main__' or 'check'.
    
    # Let's look at the serialized string.
    # Incorrect: "models.Capability.default" or similar missing 'Profile'
    # Correct: "...Profile.Capability.default"
    
    print(f"Serialized default: {serialized_string}")
    
    # The bug is that it misses the intermediate class 'Profile'.
    # So we assert that 'Profile' is present in the serialized path.
    assert 'Profile' in serialized_string, \
        f"The serialized default '{serialized_string}' does not contain 'Profile', indicating the nested class path is lost."
        
    # Also ensure it ends with .default
    assert serialized_string.endswith('.default'), \
        f"The serialized default '{serialized_string}' does not end with .default"

if __name__ == '__main__':
    try:
        check_migration_serialization()
        print("Check passed: The issue is fixed.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Check failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
