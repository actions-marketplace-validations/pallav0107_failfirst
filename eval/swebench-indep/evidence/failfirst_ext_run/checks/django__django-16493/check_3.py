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

from django.core.files.storage import default_storage
from django.db import models

def get_default_storage():
    return default_storage

class TestModel(models.Model):
    # This field uses a callable that returns default_storage
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
    # Currently (buggy behavior), it is omitted because self.storage evaluates to default_storage
    # and the check `self.storage is not default_storage` fails.
    
    # Correct behavior: 'storage' key should be present in kwargs pointing to the callable
    assert 'storage' in kwargs, (
        "FAILED: 'storage' kwarg is missing from deconstructed field. "
        "The callable storage was incorrectly omitted."
    )
    
    # Verify it points to our specific callable
    assert kwargs['storage'] == get_default_storage, (
        f"FAILED: Expected storage to be {get_default_storage}, got {kwargs['storage']}"
    )
    
    print("PASSED: Callable storage returning default_storage is correctly preserved in deconstruct().")
    sys.exit(0)

if __name__ == '__main__':
    main()
