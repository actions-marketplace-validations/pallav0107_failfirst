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

# Define models
class Photo(models.Model):
    class Meta:
        app_label = 'test_app'

class Report(models.Model):
    photos = models.ManyToManyField(Photo)
    
    class Meta:
        app_label = 'test_app'

# Create tables
from django.core.management import call_command
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Photo)
    schema_editor.create_model(Report)
    # Create the through model table
    schema_editor.create_model(Report.photos.through)

# Define Inline Admin
class ReportPhotoInlineModelAdmin(admin.TabularInline):
    model = Report.photos.through
    show_change_link = True

class ReportAdmin(admin.ModelAdmin):
    inlines = [ReportPhotoInlineModelAdmin]

# Register models
admin_site = AdminSite()
admin_site.register(Report, ReportAdmin)
admin_site.register(Photo)

# Create a user with only view permission
user = User.objects.create_user(username='viewer', password='password')
content_type = ContentType.objects.get_for_model(Report)
view_perm = Permission.objects.get(codename='view_report', content_type=content_type)
user.user_permissions.add(view_perm)

# Create a request simulating the user
factory = RequestFactory()
request = factory.get('/admin/test_app/report/1/change/')
request.user = user

# Get the inline admin instance
report_admin = admin_site._registry[Report]
inline_admin = None
for inline in report_admin.inlines:
    if isinstance(inline, type) and issubclass(inline, admin.BaseInlineFormSet):
        pass # This logic is slightly off, let's get it properly
    
# Let's instantiate the inline properly
from django.contrib.admin.options import InlineModelAdmin

# Find the inline class registered
inline_class = ReportAdmin.inlines[0]
inline_instance = inline_class(Report, admin_site)

# Check if the inline has read-only fields set for users with only view permission
# The bug is that users with view permission can still edit the inline.
# If fixed, the fields should be read-only or the inline should not allow additions/deletions.

# We check the get_readonly_fields method or has_add_permission/has_delete_permission
# For a user with only view permission, has_add_permission and has_delete_permission should return False

# Create a dummy object to test permissions
report = Report.objects.create()

# Check permissions on the inline
has_add = inline_instance.has_add_permission(request)
has_delete = inline_instance.has_delete_permission(request)
has_change = inline_instance.has_change_permission(request)

# The issue states that users with ONLY view permission can add/remove items.
# Correct behavior: has_add and has_delete should be False for view-only users.
# Note: has_change might be True if view implies seeing the change form, but editing specific fields
# should be restricted. However, for M2M inlines, adding/removing is done via add/delete permissions 
# of the inline formset.

# Assert that a view-only user cannot add or delete inlines
assert has_add is False, f"View-only user should not have add permission on inline, but got {has_add}"
assert has_delete is False, f"View-only user should not have delete permission on inline, but got {has_delete}"

print("Check passed: View-only users cannot edit M2M inlines.")
sys.exit(0)
