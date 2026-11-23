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
            'django.contrib.postgres',  # Needed for ArrayField
        ],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.management import call_command
from io import StringIO
import tempfile
import shutil

# Define the model structure as described in the issue
class Profile(models.Model):
    class Capability(models.TextChoices):
        BASIC = ("BASIC", "Basic")
        PROFESSIONAL = ("PROFESSIONAL", "Professional")

        @classmethod
        def default(cls) -> list[str]:
            return [cls.BASIC]

    capabilities = ArrayField(
        models.CharField(choices=Capability.choices, max_length=30, blank=True),
        null=True,
        default=Capability.default
    )

    class Meta:
        app_label = 'test_app'

def check_migration_serialization():
    """
    Check if the migration serializer correctly resolves the path to the nested class method.
    The issue states that the migration contains 'appname.models.Capability.default' 
    instead of 'appname.models.Profile.Capability.default'.
    
    We will use Django's migration writer to serialize the field and check the output.
    """
    from django.db.migrations.writer import MigrationWriter
    from django.db.migrations.operations.fields import AddField
    
    # Create a dummy operation to test serialization
    operation = AddField(
        model_name='profile',
        name='capabilities',
        field=Profile._meta.get_field('capabilities'),
    )
    
    # Serialize the operation
    try:
        writer = MigrationWriter([operation])
        output = writer.as_string()
        
        # The correct reference should include the parent class 'Profile'
        # i.e., 'test_app.models.Profile.Capability.default'
        # The bug produces 'test_app.models.Capability.default'
        
        # We look for the string representation in the generated migration code
        # Note: The exact app label might vary, but the structure is key.
        
        # Let's extract the specific line or check if the wrong path exists
        # The bug report says the wrong value is "appname.models.Capability.default"
        # The correct value is "appname.models.Profile.Capability.default"
        
        # Since we are using 'test_app', we expect:
        # Correct: test_app.models.Profile.Capability.default
        # Wrong:   test_app.models.Capability.default
        
        if 'models.Capability.default' in output and 'models.Profile.Capability.default' not in output:
            # This indicates the bug is present (missing Profile in the path)
            raise AssertionError("Bug detected: Migration serialization uses incorrect path 'models.Capability.default' instead of 'models.Profile.Capability.default'")
        
        # If the correct path is present, the issue is fixed
        assert 'models.Profile.Capability.default' in output, f"Expected 'models.Profile.Capability.default' in migration output, but got:\n{output}"
        
    except Exception as e:
        if isinstance(e, AssertionError):
            raise
        raise AssertionError(f"Failed to serialize migration: {e}")

if __name__ == '__main__':
    try:
        check_migration_serialization()
        print("Check passed: The issue is fixed.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Check failed: {e}")
        sys.exit(1)
