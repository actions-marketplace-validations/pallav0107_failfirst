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
        SECRET_KEY='test-secret-key',
    )

django.setup()

from django.contrib import admin
from django.db import models


# Define a simple model
class City(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'admin_checks'


# Define a ModelAdmin with an invalid readonly_field (a non-existent field name)
class CityAdmin(admin.ModelAdmin):
    readonly_fields = ['non_existent_field']


def check_error_message():
    """
    Check if the error message for readonly_fields includes the field name.
    
    The issue states that the current error message is:
    "The value of 'readonly_fields[0]' is not a callable, an attribute of 'CityInline', or an attribute of 'admin_checks.City'."
    
    It should be unified with other fields like list_editable to include the field name, e.g.:
    "The value of 'readonly_fields[0]' refers to 'non_existent_field', which is not..."
    """
    try:
        # Trigger the check by creating an instance and accessing checks
        ma = CityAdmin(City, admin.site)
        errors = ma.check()
        
        # If there are no errors, something is wrong with our test setup
        assert len(errors) > 0, "Expected validation errors but got none"
        
        # Get the first error message
        error_msg = str(errors[0])
        
        # Check if the field name 'non_existent_field' is in the error message
        # The fix should include the field name in the error message
        assert 'non_existent_field' in error_msg, \
            f"Error message should include the field name 'non_existent_field'. Got: {error_msg}"
            
        return True
        
    except Exception as e:
        print(f"Unexpected error during check: {e}", file=sys.stderr)
        raise


if __name__ == '__main__':
    try:
        check_error_message()
        print("PASS: Error message correctly includes the field name.")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
