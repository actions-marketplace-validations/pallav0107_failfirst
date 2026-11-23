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
            'django.contrib.admin',
        ],
        ROOT_URLCONF='',
        SECRET_KEY='test-secret-key',
    )

django.setup()

from django.contrib import admin
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test import RequestFactory
from django.contrib.admin.sites import AdminSite

# Define models dynamically to avoid file creation
class Photo(models.Model):
    class Meta:
        app_label = 'test_app'

class Report(models.Model):
    photos = models.ManyToManyField(Photo)
    
    class Meta:
        app_label = 'test_app'

# Create the through model reference
ReportPhotoThrough = Report.photos.through

# Register inline
class ReportPhotoInlineModelAdmin(admin.TabularInline):
    model = ReportPhotoThrough
    show_change_link = True

class ReportAdmin(admin.ModelAdmin):
    inlines = [ReportPhotoInlineModelAdmin]

# Setup database tables
from django.core.management import call_command
from django.db import connection

with connection.schema_editor() as schema_editor:
    # Create tables for our dynamic models
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    
    # We need to create tables for auth and contenttypes as well since we configured them
    # But since we are using in-memory sqlite and dynamic models, let's just create what we need.
    # Actually, calling migrate might be complex without migrations files.
    # Let's use create_table directly via schema editor if possible, or just rely on the fact that 
    # Django's test infrastructure usually handles this. Since we can't use test harness, 
    # we'll try to create tables manually.
    
    # Get all models from installed apps that are not abstract
    from django.apps import apps
    from django.contrib.contenttypes.models import ContentType as CT
    
    # Create tables for auth, contenttypes, sessions etc if needed? 
    # For this specific check, we mainly need the admin permission checking logic.
    # We can mock the database part or use a simple approach.
    
    # Let's try to create tables for our specific models and the required django contrib models.
    # This is tricky without migrations. Let's try a different approach:
    # Use Django's test client or request factory with mocked permissions?
    # No, the issue is about has_add_permission / has_change_permission on the inline.
    
    pass

# Instead of full DB setup, let's inspect the code logic directly.
# The issue is that users with only 'view' permission can edit inlines for M2M auto-created through models.
# In Django Admin, InlineModelAdmin uses has_add_permission and has_change_permission.
# For TabularInline/StackedInline, these methods check the user's permissions on the related model.
# The bug is that for auto-created M2M through models, the permission check might be missing or incorrect.

# Let's look at how Django 3.0 handles this.
# We will instantiate the admin classes and check the permission methods.

from django.contrib.auth.models import AnonymousUser

# Create a mock user with only view permission
class MockUser:
    def __init__(self, has_view_only=True):
        self.has_view_only = has_view_only
        
    def has_perm(self, perm):
        # If user has only view permission, they should NOT have add or change
        if self.has_view_only:
            if perm.endswith('.add_reportphotonthrough') or perm.endswith('.change_reportphotonthrough'):
                return False
            if perm.endswith('.view_reportphotonthrough'):
                return True
        return False

    def has_module_perms(self, app_label):
        return True

# However, the actual permission check in InlineModelAdmin doesn't just rely on has_perm directly 
# in a simple way. It uses _has_model_perm or similar internal methods.
# Let's look at the source code behavior by importing and inspecting.

# In Django 3.0, InlineModelAdmin.has_add_permission checks:
# return self.has_change_permission(request, obj) or ...
# And has_change_permission checks perms on the model.

# The key is whether the admin correctly identifies that the user lacks add/change perms on the Through model.

# Let's create a minimal test case that simulates the permission check.
# We need to register the models and then check the inline's permission methods.

site = AdminSite()

report_admin = ReportAdmin(Report, site)
inline_admin = ReportPhotoInlineModelAdmin(Report, site)

# Create a mock request
factory = RequestFactory()
request = factory.get('/admin/')
request.user = MockUser(has_view_only=True)

# Check if the inline allows adding or changing
# In Django, InlineModelAdmin.has_add_permission(request, parent_obj=None)
# and has_change_permission(request, parent_obj=None)

try:
    # We need to ensure the content type exists for the through model for permission checks to work properly
    # But since we didn't create DB tables, has_perm might fail or behave unexpectedly.
    # Let's patch the permission check to simulate the environment where the user has ONLY view permission.
    
    # The core issue: Does the inline respect the lack of add/change permissions?
    # If fixed, has_add_permission and has_change_permission should return False for a view-only user.
    
    # Let's monkey-patch the user's has_perm to be precise
    original_has_perm = MockUser.has_perm
    
    def strict_has_perm(self, perm):
        # Only allow view permission
        if 'view' in perm:
            return True
        return False
        
    MockUser.has_perm = strict_has_perm
    
    # We also need to make sure get_model_perms returns the correct dict.
    # InlineModelAdmin.get_model_perms returns {'add': ..., 'change': ..., 'delete': ..., 'view': ...}
    # based on user permissions.
    
    perms = inline_admin.get_model_perms(request)
    
    # If the bug is present, perms['add'] or perms['change'] might be True even though user has no such perms.
    # If fixed, they should be False.
    
    # Note: get_model_perms calls has_add_permission, has_change_permission, etc.
    
    assert perms.get('add') == False, f"Expected add permission to be False, got {perms.get('add')}"
    assert perms.get('change') == False, f"Expected change permission to be False, got {perms.get('change')}"
    
    print("Check passed: View-only user cannot add or change inlines.")
    sys.exit(0)

except AssertionError as e:
    print(f"Check failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error during check: {e}")
    # If we can't run the check due to setup issues, we might need to adjust.
    # But given the constraints, this logical check should work if Django is importable.
    sys.exit(1)
