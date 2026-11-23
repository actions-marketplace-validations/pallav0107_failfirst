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

from django.core.files.storage import default_storage, FileSystemStorage
from django.db import models
from django.db.migrations.writer import MigrationWriter

# Define a callable that returns default_storage
def get_default_storage():
    return default_storage

# Define a callable that returns a different storage
other_storage = FileSystemStorage(location='/tmp/other')
def get_other_storage():
    return other_storage

# Create a field with the callable returning default_storage
field_with_default_callable = models.FileField(storage=get_default_storage)

# Deconstruct the field
name, path, args, kwargs = field_with_default_callable.deconstruct()

# The issue states that if the storage argument is a callable that returns default_storage,
# it should be included in the deconstructed form as a reference to the callable.
# Currently, it is omitted because self.storage evaluates to default_storage, 
# and the check `if self.storage is not default_storage` fails.

# Check if 'storage' is in kwargs
# If the bug is present, 'storage' will NOT be in kwargs.
# If the bug is fixed, 'storage' SHOULD be in kwargs because the user explicitly provided a callable.

# However, we need to be careful. The intended behavior of #31941 was to omit storage 
# if it's effectively the default. But if the user provides a callable, even if that callable 
# returns the default storage, the callable itself is part of the field definition and should 
# be preserved in migrations to ensure reproducibility and correctness of the model definition.

# Let's look at the specific claim: "it is omitted from the deconstructed form ... rather than 
# being included as a reference to the callable as expected."

# So, the fix should ensure that if a callable was passed, it is included in kwargs['storage'].

assert 'storage' in kwargs, (
    "Bug is present: 'storage' kwarg is missing from deconstruct() output when "
    "a callable returning default_storage is used. The callable should be preserved."
)

# Verify that the stored value is indeed the callable get_default_storage
assert kwargs['storage'] == get_default_storage, (
    "Bug is present: 'storage' kwarg does not match the original callable."
)

print("Check passed: The issue is fixed.")
sys.exit(0)
