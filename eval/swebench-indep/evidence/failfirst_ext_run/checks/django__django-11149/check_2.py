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
            'test_app',
        ],
        ROOT_URLCONF='',
        SECRET_KEY='test-secret-key',
        USE_TZ=True,
    )

django.setup()

# Create the test app models dynamically to avoid file creation
from django.db import models
from django.contrib import admin
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
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

# Register models with admin
class ReportPhotoInlineModelAdmin(admin.TabularInline):
    model = Report.photos.through
    show_change_link = True

class ReportAdmin(admin.ModelAdmin):
    inlines = [ReportPhotoInlineModelAdmin]

# We need to register these in the admin site
admin_site = AdminSite()
admin_site.register(Report, ReportAdmin)
admin_site.register(Photo)

# Create tables
from django.core.management import call_command
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Photo)
    schema_editor.create_model(Report)
    # Create the through table for M2M
    schema_editor.create_model(Report.photos.through)

# Create a user with only view permission
from django.contrib.auth.models import Group

# Get content types
report_ct = ContentType.objects.get_for_model(Report)
photo_ct = ContentType.objects.get_for_model(Photo)
through_ct = ContentType.objects.get_for_model(Report.photos.through)

# Create permissions
view_report_perm = Permission.objects.get(codename='view_report', content_type=report_ct)
add_report_perm = Permission.objects.get(codename='add_report', content_type=report_ct)
change_report_perm = Permission.objects.get(codename='change_report', content_type=report_ct)
delete_report_perm = Permission.objects.get(codename='delete_report', content_type=report_ct)

view_photo_perm = Permission.objects.get(codename='view_photo', content_type=photo_ct)
add_photo_perm = Permission.objects.get(codename='add_photo', content_type=photo_ct)
change_photo_perm = Permission.objects.get(codename='change_photo', content_type=photo_ct)
delete_photo_perm = Permission.objects.get(codename='delete_photo', content_type=photo_ct)

# For the through model (auto-created), permissions might be named differently or not exist explicitly in some versions
# Let's check what permissions exist for the through model
through_perms = Permission.objects.filter(content_type=through_ct)
# print(list(through_perms.values_list('codename', flat=True))) # Debug if needed

# Create a user with ONLY view permissions on Report and Photo
user = User.objects.create_user(username='viewer', password='password')
user.user_permissions.add(view_report_perm)
user.user_permissions.add(view_photo_perm)

# Note: In Django 3.0, auto-created M2M through models do not have explicit permissions created by default 
# unless specified. However, the admin checks permissions on the inline model.
# The issue is that users with view-only access can still edit inlines.

# Let's simulate an admin request to check if the inline is editable
factory = RequestFactory()

# Create some data
photo1 = Photo.objects.create()
photo2 = Photo.objects.create()
report = Report.objects.create()
report.photos.add(photo1)

# Create a mock request
request = factory.get('/admin/test_app/report/1/change/')
request.user = user

# Get the ModelAdmin instance
report_admin = admin_site._registry[Report]

# Check if the user has permission to change the report
assert not report_admin.has_change_permission(request, obj=report), "User should not have change permission on Report"

# Check if the user has permission to add/delete via inline
# The core of the bug: even with view-only permission, the inline formset allows changes.
# We need to check if the inline model admin respects the user's permissions.

inline_admin = ReportPhotoInlineModelAdmin(Report, admin_site)

# Check permissions on the inline
# In Django admin, inlines typically check the parent's permissions or their own.
# For M2M inlines, it's tricky.

# Let's check if the inline formset is read-only for this user.
# If the bug exists, the formset will allow modifications.
# If fixed, it should be read-only or raise permission denied.

# A robust way to check is to see if the inline admin returns True for has_add_permission, has_change_permission, etc.
# But for M2M inlines, the permissions are often derived from the related model.

# Let's check the specific behavior reported: "editable if the user only has the view permission".
# This means the user can add/remove items in the inline.

# We will check if the inline admin allows adding/deleting for a view-only user.
# The fix usually involves making the inline read-only when the user doesn't have change/add/delete permissions.

# Check if the inline has_add_permission returns False for view-only user
try:
    # In Django 3.0, the inline might not strictly check permissions for M2M through models
    # if the user has view permission on the parent.
    
    # Let's try to get the formset
    from django.forms.models import modelformset_factory
    
    # Actually, let's look at the inline's get_queryset and form handling.
    # A simpler check: does the inline admin think the user can add/change?
    
    # For TabularInline, has_add_permission is checked.
    # If the user only has view permission on the parent and related model, 
    # they should NOT be able to add/remove in the inline.
    
    # In Django 3.0, there was a regression where view permission allowed editing inlines.
    
    # Let's assert that the inline does NOT allow adding for a view-only user.
    # Note: has_add_permission for inlines often checks the parent's has_add_permission.
    # But for M2M, it's about the through model.
    
    # The correct behavior is that the inline should be read-only or hidden.
    # If the bug is present, the inline fields will be editable.
    
    # We can check if the inline's formset is marked as readonly or if permissions prevent saving.
    
    # Let's check the permission methods directly on the inline admin instance
    # Note: Inline admins don't always have standard permission methods like ModelAdmin.
    # They rely on the parent ModelAdmin's permissions mostly.
    
    # However, for M2M inlines, the ability to add/remove is controlled by the 
    # user's permission on the related model or the through model.
    
    # The issue states that with VIEW permission, the user can ADD/REMOVE.
    # This implies that has_add_permission or equivalent is returning True incorrectly.
    
    # Let's check if the user can actually save changes to the M2M relationship via admin.
    # This is complex to simulate fully without a POST request.
    
    # Alternative approach: Check if the inline formset allows extra forms (adding) or deletion.
    # If the user has no add/change/delete permissions, the inline should be read-only.
    
    # In Django 3.0, the fix involved checking permissions more strictly for inlines.
    
    # Let's verify the permission check logic.
    # If the user only has 'view' permission, they should not be able to modify the M2M.
    
    # We'll check if the inline admin's has_add_permission returns False.
    # For inlines, has_add_permission takes obj (the parent instance).
    
    # In Django source, InlineModelAdmin.has_add_permission calls parent_model_admin.has_add_permission.
    # Since our user doesn't have add_report permission, this should be False.
    # BUT, for M2M inlines, sometimes the logic is different.
    
    # Let's check the actual permission result.
    can_add = inline_admin.has_add_permission(request, obj=report)
    can_change = inline_admin.has_change_permission(request, obj=report)
    can_delete = inline_admin.has_delete_permission(request, obj=report)
    
    # If the bug is fixed, these should all be False for a view-only user.
    # If the bug exists, one of them might be True, allowing edits.
    
    # According to the ticket, the regression allows adding/removing.
    # So if can_add or can_delete is True, the bug exists.
    
    # Wait, for M2M inlines, the permissions might be checked against the related model (Photo).
    # The user has view_photo but not add_photo/change_photo/delete_photo.
    
    # Let's assume the fix ensures that if the user lacks add/change/delete on the related/through model,
    # the inline is read-only.
    
    # Assert that the user cannot add, change, or delete via the inline.
    assert not can_add, "View-only user should not have add permission in inline"
    assert not can_change, "View-only user should not have change permission in inline"
    assert not can_delete, "View-only user should not have delete permission in inline"
    
except Exception as e:
    # If any assertion fails, it means the bug is present (or our check is wrong)
    # We want to exit with non-zero if bug is present.
    # AssertionError will be raised by assert statements.
    raise

print("Check passed: View-only user cannot edit M2M inlines.")
sys.exit(0)
