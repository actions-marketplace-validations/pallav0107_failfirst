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
        app_label = 'test_app'

# Define a ModelAdmin with an invalid readonly_fields entry
class CityAdmin(admin.ModelAdmin):
    readonly_fields = ['non_existent_field']

def check_error_message():
    """
    Check if the error message for readonly_fields includes the field name.
    
    The issue states that the current error message is:
    "The value of 'readonly_fields[0]' is not a callable, an attribute of 'CityInline', or an attribute of 'admin_checks.City'."
    
    And it should be unified with other fields like list_editable to include the field name:
    "The value of 'readonly_fields[0]' refers to 'non_existent_field', which is not..."
    """
    try:
        # Trigger the check by creating the ModelAdmin instance
        # The check happens during __init__ or when accessing certain properties
        admin_site = admin.AdminSite()
        city_admin = CityAdmin(City, admin_site)
        
        # Force validation/checking of readonly_fields
        # This usually happens when getting the readonly fields for an object
        # Let's try to get the readonly fields which should trigger the check
        from django.contrib.admin.utils import flatten_fieldsets
        
        # The actual check is performed in ModelAdmin.get_readonly_fields
        # But the system check framework is where this specific error comes from
        # Let's look at how Django performs these checks
        
        # In Django, these checks are part of the system check framework
        # specifically admin.E035 for readonly_fields
        
        # We need to trigger the system checks
        from django.core.management import call_command
        from io import StringIO
        
        stderr = StringIO()
        try:
            call_command('check', '--deploy', stderr=stderr)
        except SystemExit:
            pass
            
        # Actually, let's directly test the check function
        from django.contrib.admin.checks import ModelAdminCheck
        from django.contrib.admin.options import ModelAdmin
        
        # Create an instance to check
        check_instance = ModelAdminCheck()
        
        # Run the check for our CityAdmin
        errors = check_instance._check_readonly_fields(CityAdmin, City)
        
        if not errors:
            # If there are no errors, something is wrong with our test setup
            # because 'non_existent_field' should definitely cause an error
            print("ERROR: No validation errors found for invalid readonly_fields")
            sys.exit(1)
            
        # Get the first error message
        error_msg = str(errors[0])
        
        print(f"Error message: {error_msg}")
        
        # Check if the field name is included in the error message
        # The fix should make the error message include 'non_existent_field'
        if 'non_existent_field' in error_msg:
            print("SUCCESS: Field name is included in the error message")
            sys.exit(0)
        else:
            print("FAILURE: Field name is NOT included in the error message")
            # Assert to ensure non-zero exit code
            assert 'non_existent_field' in error_msg, f"Field name 'non_existent_field' not found in error message: {error_msg}"
            
    except Exception as e:
        print(f"Exception occurred: {e}")
        # If we get an exception, it might be because the check works differently
        # Let's try another approach - directly calling the check method
        
        # Re-import and try the direct check approach
        from django.contrib.admin import site
        from django.contrib.admin.checks import _check_readonly_fields_item
        
        # Get the registered admin or create a temporary one
        temp_admin = CityAdmin(City, site)
        
        # The check is done per item in readonly_fields
        # Let's manually check what error would be raised
        
        # Looking at Django source, the check is in contrib/admin/checks.py
        # Method: _check_readonly_fields_item
        
        # Let's just verify the current behavior by examining the error
        # When we access readonly_fields property, it might trigger validation
        
        try:
            # This should trigger the validation
            readonly = temp_admin.get_readonly_fields(None)
        except Exception as validation_error:
            error_msg = str(validation_error)
            print(f"Validation error message: {error_msg}")
            
            if 'non_existent_field' in error_msg:
                print("SUCCESS: Field name is included in the validation error")
                sys.exit(0)
            else:
                print("FAILURE: Field name is NOT included in the validation error")
                assert 'non_existent_field' in error_msg, f"Field name 'non_existent_field' not found in error message: {error_msg}"
        
        # If no exception was raised, the check might happen elsewhere
        # Let's use the system check framework properly
        
        from django.core.checks import run_checks, Tags
        
        all_errors = run_checks(tags=[Tags.admin])
        
        # Filter errors related to our CityAdmin
        relevant_errors = [e for e in all_errors if 'CityAdmin' in str(e) or 'non_existent_field' in str(e)]
        
        if relevant_errors:
            error_msg = str(relevant_errors[0])
            print(f"System check error: {error_msg}")
            
            if 'non_existent_field' in error_msg:
                print("SUCCESS: Field name is included in the system check error")
                sys.exit(0)
            else:
                print("FAILURE: Field name is NOT included in the system check error")
                assert 'non_existent_field' in error_msg, f"Field name 'non_existent_field' not found in error message: {error_msg}"
        else:
            print("No relevant errors found in system checks")
            sys.exit(1)

if __name__ == '__main__':
    check_error_message()
