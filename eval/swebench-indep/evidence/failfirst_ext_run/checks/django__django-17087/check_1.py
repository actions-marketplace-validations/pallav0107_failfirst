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

    # We don't need to actually create the table, just inspect the migration generation
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
    """
    field = Profile._meta.get_field('capabilities')
    
    # Get the deconstructed field arguments
    name, path, args, kwargs = field.deconstruct()
    
    # The 'default' key should be present in kwargs
    assert 'default' in kwargs, "Default argument missing from deconstructed field"
    
    default_value = kwargs['default']
    
    # Serialize the operation to see what string representation is generated
    # We simulate an AddField operation
    from django.db.migrations.operations.fields import AddField
    
    operation = AddField(
        model_name='profile',
        name='capabilities',
        field=field,
    )
    
    writer = MigrationWriter([operation], 'test_migration')
    
    # Get the string representation of the migration file
    output = writer.as_string()
    
    # The issue states that the wrong value "appname.models.Capability.default" is generated.
    # The correct value should include the parent class: "appname.models.Profile.Capability.default".
    # Since our app_label is 'test_app', we expect 'test_app.models.Profile.Capability.default'.
    
    # Check if the incorrect serialization is present
    incorrect_ref = "models.Capability.default"
    correct_ref = "models.Profile.Capability.default"
    
    # If the bug exists, the output will contain the incorrect reference without the parent class
    # If fixed, it should contain the full path including the parent class
    
    if incorrect_ref in output and correct_ref not in output:
        raise AssertionError(f"Bug reproduced: Migration contains incorrect reference '{incorrect_ref}' instead of '{correct_ref}'. Output snippet: ...{output[output.find(incorrect_ref)-20:output.find(incorrect_ref)+len(incorrect_ref)+20]}...")
    
    # Also verify that the correct reference IS in the output
    if correct_ref not in output:
        # It might be serialized differently, but let's check if it's at least validly serializable
        # Try to execute the migration string to see if it fails? No, too complex.
        # Let's stick to the string check which is what the issue describes.
        raise AssertionError(f"Expected correct reference '{correct_ref}' not found in migration output.")

if __name__ == '__main__':
    try:
        check_migration_serialization()
        print("Check passed: Behaviour is correct (issue is fixed).")
        sys.exit(0)
    except AssertionError as e:
        print(f"Check failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
