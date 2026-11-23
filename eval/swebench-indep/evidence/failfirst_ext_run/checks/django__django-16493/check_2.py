import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_settings')

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

from django.core.files.storage import default_storage
from django.db import models

def get_default_storage():
    return default_storage

class TestModel(models.Model):
    # Create a FileField with a callable that returns default_storage
    my_file = models.FileField(storage=get_default_storage)

    class Meta:
        app_label = 'test_app'

def main():
    # Get the field instance
    field = TestModel._meta.get_field('my_file')
    
    # Deconstruct the field
    name, path, args, kwargs = field.deconstruct()
    
    # The issue states that if storage is a callable returning default_storage,
    # it should be included in the deconstructed kwargs as a reference to the callable.
    # Currently (buggy behavior), it is omitted because self.storage evaluates to default_storage.
    
    # Check if 'storage' is in kwargs
    if 'storage' in kwargs:
        # If it is present, check if it refers to our callable
        storage_val = kwargs['storage']
        # It should be the function itself or a reference to it
        if storage_val == get_default_storage:
            print("PASS: Callable storage correctly included in deconstruction.")
            sys.exit(0)
        else:
            # It might be serialized differently, but for a local function, 
            # it should ideally be the function object or a valid reference.
            # However, the primary bug is omission. If it's present and not the right value,
            # we need to be careful. But usually, deconstruct passes the callable directly.
            print(f"FAIL: Storage key present but value is unexpected: {storage_val}")
            sys.exit(1)
    else:
        # This is the buggy behavior described in the issue
        print("FAIL: 'storage' kwarg is missing from deconstruction when callable returns default_storage.")
        sys.exit(1)

if __name__ == '__main__':
    main()
