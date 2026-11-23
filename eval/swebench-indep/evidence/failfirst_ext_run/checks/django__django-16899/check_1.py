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
        SECRET_KEY='test-secret-key',
    )

django.setup()

from django.db import models
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured

# Define a simple model
class City(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'myapp'

# Define a ModelAdmin with an invalid readonly_field (a field that doesn't exist)
class CityAdmin(admin.ModelAdmin):
    readonly_fields = ('non_existent_field',)

# Create the admin instance
admin_instance = CityAdmin(City, admin.site)

# Trigger the checks by accessing the validated readonly_fields or calling check method
# The check happens during initialization or when accessing certain properties.
# Specifically, django.contrib.admin.checks.register runs checks.
# We can manually trigger the check for readonly_fields.

from django.contrib.admin.checks import ModelAdminChecker

checker = ModelAdminChecker()
errors = checker.check_readonly_fields(admin_instance, City)

# If there are no errors, something is wrong with our test setup because 'non_existent_field' should fail.
if not errors:
    print("ERROR: Expected validation error for non-existent field in readonly_fields, but got none.")
    sys.exit(1)

error_message = str(errors[0].msg)

print(f"Error message generated: {error_message}")

# The issue states that the error message SHOULD include the field name.
# Old behavior: "The value of 'readonly_fields[0]' is not a callable..."
# New/Fixed behavior: Should mention 'non_existent_field'.

assert 'non_existent_field' in error_message, f"The error message does not include the field name 'non_existent_field'. Message was: {error_message}"

print("Success: The error message correctly includes the field name.")
sys.exit(0)
