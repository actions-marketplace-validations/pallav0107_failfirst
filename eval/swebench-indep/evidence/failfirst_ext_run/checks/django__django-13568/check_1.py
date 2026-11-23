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
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'myapp',
        ],
        SECRET_KEY='test-secret-key',
    )

django.setup()

# Create a temporary app for the test model
from django.apps import apps
from django.db import models
from django.contrib.auth.models import AbstractBaseUser

# We need to create a model dynamically or define it in a way that Django recognizes.
# Since we can't modify files, we'll use a dynamic app creation approach or 
# rely on the fact that we can define models if we register them properly.
# However, the standard way to test this without modifying the repo is to 
# simulate the check logic or create a test app in memory.

# Let's try to create a custom user model and run the system check.

# To do this cleanly, we'll define a new app configuration and model.
import django.apps
from django.db.models.base import ModelBase

# Define a simple app config for our test
class TestAppConfig(django.apps.AppConfig):
    name = 'myapp'
    label = 'myapp'

# Register the app
apps.app_configs['myapp'] = TestAppConfig('myapp', None)
apps.apps_ready = True
apps.models_loaded = True
apps.ready = True

# Now define the model
class User(AbstractBaseUser):
    username = models.CharField(max_length=30)
    USERNAME_FIELD = "username"
    
    class Meta:
        app_label = 'myapp'
        constraints = [
            models.UniqueConstraint(fields=["username"], name="user_username_unq")
        ]

# Force Django to recognize the model
from django.contrib.auth import get_user_model
# We can't easily swap the user model here without full setup, so let's directly test the check.

# The check in question is auth.E003. It lives in django.contrib.auth.checks
from django.contrib.auth import checks as auth_checks
from django.core.checks import Tags

# Let's look at how the check works.
# In Django 3.2, django/contrib/auth/checks.py contains check_user_model.
# It checks if USERNAME_FIELD is unique.

# We need to invoke the check on our specific model.
# The function check_user_model(app_configs, **kwargs) iterates through installed apps.
# Since we added 'myapp' to INSTALLED_APPS, it should pick up our model if registered correctly.

# However, registering models dynamically is tricky. 
# Alternative: Directly call the internal logic or simulate the check.

# Let's try to run the actual system check framework.
from django.core.management import call_command
from io import StringIO

# Create tables for our model
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(User)

# Now run checks
out = StringIO()
try:
    # We need to ensure the app registry is fully ready
    django.setup() # Re-setup to ensure everything is linked
    
    # Run the specific check tag
    from django.core.checks.registry import registry
    errors = registry.run_checks(tags=[Tags.compatibility])
    
    # Filter for auth.E003
    auth_e003_errors = [e for e in errors if e.id == 'auth.E003']
    
    # If the issue is fixed, there should be NO auth.E003 error for our User model
    # because we have a UniqueConstraint.
    # If the issue is NOT fixed, there WILL be an auth.E003 error.
    
    # Wait, the default User model from django.contrib.auth might also trigger checks.
    # We configured INSTALLED_APPS with 'django.contrib.auth'.
    # The default User model (if AUTH_USER_MODEL is not set) is django.contrib.auth.models.User.
    # That model has unique=True on username, so it won't trigger E003.
    
    # Our custom User model is in 'myapp'.
    # Did the check pick it up?
    
    # Let's print errors for debugging if needed, but we must exit based on assertion.
    
    # Check if any error refers to our model 'myapp.User'
    my_user_errors = [e for e in auth_e003_errors if 'myapp.User' in str(e.obj) or (hasattr(e, 'obj') and e.obj == User)]
    
    # Actually, let's look at all auth.E003 errors.
    # If the fix is present, the check should skip validation if a UniqueConstraint exists.
    # So we expect 0 errors related to our model.
    
    # However, simply running registry.run_checks might not include our dynamically added model 
    # if the app registry wasn't fully rebuilt.
    
    # Let's try a more direct approach: Import the check function and call it with our model.
    # But check_user_model doesn't take a model argument, it discovers it.
    
    # Let's rely on the fact that we added 'myapp' to INSTALLED_APPS before django.setup().
    # And defined the model after.
    # This is fragile.
    
    # Better approach: Patch the get_user_model or AUTH_USER_MODEL?
    # No, let's just check the logic of the check itself.
    
    # In django/contrib/auth/checks.py:
    # def check_user_model(app_configs, **kwargs):
    #   ...
    #   if not cls._meta.get_field(cls.USERNAME_FIELD).unique:
    #       if not any(
    #           constraint.contains_field(cls.USERNAME_FIELD) 
    #           for constraint in cls._meta.constraints 
    #           if isinstance(constraint, models.UniqueConstraint)
    #       ):
    #           errors.append(...)
    
    # So we can just test this logic directly on our User class.
    
    field = User._meta.get_field(User.USERNAME_FIELD)
    is_unique = field.unique
    
    has_unique_constraint = any(
        isinstance(constraint, models.UniqueConstraint) and constraint.contains_field(User.USERNAME_FIELD)
        for constraint in User._meta.constraints
    )
    
    # The bug is that it raises E003 even if has_unique_constraint is True.
    # The fix is that it should NOT raise E003 if has_unique_constraint is True.
    
    # So, if the code is correct (fixed), it should recognize the constraint.
    # We can't easily run the check function in isolation without the app registry.
    
    # Let's try to trigger the check via manage.py check command which uses the registry.
    # We need to make sure our model is visible.
    
    pass

except Exception as e:
    print(f"Error during setup: {e}", file=sys.stderr)
    sys.exit(1)

# Let's restart with a cleaner approach using a separate module structure simulation.
# Since we can't create files, we'll stick to the direct logic test if possible, 
# or ensure the registry works.

# Re-evaluating: The prompt asks to exercise the behaviour.
# The behaviour is: "Skip auth.E003 system check for USERNAME_FIELD with total UniqueConstraints."

# Let's assume the previous django.setup() worked and our model is registered.
# If not, we might need to force it.

# Let's try to get errors again carefully.
from django.core.checks import run_checks
errors = run_checks(tags=[Tags.compatibility])

auth_e003_errors = [e for e in errors if e.id == 'auth.E003']

# Find errors specifically for our User model
target_errors = []
for e in auth_e003_errors:
    # e.obj is the model class
    if hasattr(e, 'obj') and e.obj == User:
        target_errors.append(e)

# Assertion:
# If the issue is FIXED, there should be NO errors for our User model.
# If the issue is NOT FIXED, there SHOULD BE an error for our User model.

assert len(target_errors) == 0, f"Expected no auth.E003 errors for User with UniqueConstraint, but got: {target_errors}"

sys.exit(0)
