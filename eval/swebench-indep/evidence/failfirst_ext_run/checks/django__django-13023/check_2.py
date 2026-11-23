import os
import sys

# Configure Django settings before importing Django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
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
    )

django.setup()

from django.core.exceptions import ValidationError
from django.db.models import DecimalField

def main():
    # Create a DecimalField instance
    field = DecimalField(max_digits=10, decimal_places=2)
    
    # The issue states that passing a dict to to_python raises TypeError
    # instead of ValidationError. We expect it to raise ValidationError
    # after the fix.
    
    try:
        # Call to_python with a dictionary value
        result = field.to_python({'key': 'value'})
        # If it doesn't raise an exception, that's also incorrect behavior
        # but the issue specifically mentions TypeError vs ValidationError.
        # Usually invalid input should raise ValidationError.
        print("ERROR: No exception was raised for dict input.")
        sys.exit(1)
    except ValidationError:
        # This is the expected behavior after the fix
        sys.exit(0)
    except TypeError as e:
        # This is the buggy behavior described in the issue
        print(f"BUG: TypeError raised instead of ValidationError: {e}")
        sys.exit(1)
    except Exception as e:
        # Any other unexpected exception
        print(f"UNEXPECTED: {type(e).__name__} raised: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
