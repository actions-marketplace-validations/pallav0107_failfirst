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
            'myapp',
        ],
        ROOT_URLCONF='',
        SECRET_KEY='test-secret-key',
    )

django.setup()

# Create a temporary app for the test model
from django.apps import apps
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

# Define the custom user model as described in the issue
class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None):
        if not username:
            raise ValueError('The Username field must be set')
        user = self.model(username=username)
        user.set_password(password)
        user.save(using=self._db)
        return user

class CustomUser(AbstractBaseUser):
    username = models.CharField(max_length=30)
    
    USERNAME_FIELD = "username"
    
    objects = CustomUserManager()

    class Meta:
        app_label = 'myapp'
        constraints = [
            models.UniqueConstraint(fields=["username"], name="user_username_unq")
        ]

# Import the system check
from django.core.checks import run_checks
from django.contrib.auth.checks import check_user_model

# We need to register the model properly so Django knows about it.
# Since we are using a dynamic app label 'myapp', we need to ensure 
# the app registry is aware of it or just run the specific check logic.

# The most direct way to test this is to invoke the specific check function
# that generates auth.E003.

# Let's look at how check_user_model works. It iterates over installed apps
# looking for the user model. Since we added 'myapp' to INSTALLED_APPS but 
# didn't create a real module, we might face issues with the app registry.

# Alternative approach: Manually construct the scenario and call the check logic
# or use Django's check framework on a properly defined model.

# To make this robust without creating files, let's try to trigger the check
# by simulating the environment. However, `check_user_model` relies on 
# `apps.get_model(settings.AUTH_USER_MODEL)`. 

# Let's set AUTH_USER_MODEL to our custom model.
# But our model is defined in __main__ or dynamically. 
# Django expects app_label.ModelName.

# Let's try a different angle: Inspect the source of the check or 
# replicate the logic. The check `auth.E003` is raised in 
# `django/contrib/auth/checks.py`.

# Logic from Django 3.2 (approximate):
# def check_user_model(app_configs=None, **kwargs):
#     ...
#     username_field = getattr(user_model, 'USERNAME_FIELD', None)
#     if username_field:
#         f = user_model._meta.get_field(username_field)
#         if not f.unique:
#             # Check constraints? In the buggy version, it does NOT check constraints.
#             # In the fixed version, it SHOULD check constraints.
#             pass

# Let's actually try to run the system checks after setting up the model correctly.
# We need to make sure 'myapp' is a valid app in the registry.

from django.apps.registry import Apps
from django.core.management import call_command

# Re-configure with a more standard setup if possible, but we can't create files.
# Let's stick to the current setup but ensure the model is registered.

# Actually, the simplest way to test this specific behavior change is to 
# instantiate the check logic directly against the model class we defined.

def get_auth_e003_errors(model_class):
    """
    Replicates the logic of check_user_model regarding E003 to see if 
    it respects UniqueConstraints.
    """
    errors = []
    username_field_name = getattr(model_class, 'USERNAME_FIELD', None)
    
    if username_field_name:
        try:
            field = model_class._meta.get_field(username_field_name)
        except Exception:
            return errors
            
        # Original buggy logic: only checks field.unique
        # Fixed logic: should also check for UniqueConstraint
        
        is_unique_via_field = field.unique
        
        # Check for unique constraint
        is_unique_via_constraint = False
        for constraint in model_class._meta.constraints:
            if isinstance(constraint, models.UniqueConstraint):
                # Check if the constraint covers exactly the username field
                # Note: Constraints can have expressions, conditions, etc.
                # Simple case: fields tuple matches
                if hasattr(constraint, 'fields') and constraint.fields == (username_field_name,):
                    is_unique_via_constraint = True
                    break
        
        if not is_unique_via_field and not is_unique_via_constraint:
            # This would trigger E003
            from django.core.checks import Error
            errors.append(
                Error(
                    "'%s.%s' must be unique because it is named as the 'USERNAME_FIELD'." % (
                        model_class._meta.object_name,
                        username_field_name,
                    ),
                    obj=model_class,
                    id='auth.E003',
                )
            )
            
    return errors

# Test the model defined above
errors = get_auth_e003_errors(CustomUser)

# If the issue is FIXED, the system check should recognize the UniqueConstraint
# and NOT raise E003. Therefore, errors should be empty.
# If the issue is NOT FIXED (or if we are testing the bug existence), 
# the naive check above mimics the OLD behavior? No, wait.

# The prompt asks: "Exit with status 0 if and only if the behaviour is correct, 
# meaning the issue has been fixed."

# The issue reports that E003 IS triggered even when a UniqueConstraint exists.
# The desired behavior (fix) is that E003 is SKIPPED if a UniqueConstraint exists.

# My helper function `get_auth_e003_errors` implements the CORRECT logic 
# (checking both field.unique and constraints). 
# If I use this helper, it will always return no errors for our model, 
# which doesn't test the actual Django code.

# I must test the ACTUAL Django code.

# Let's try to run the real Django check.
# We need to register the app 'myapp' properly.

import types

# Create a mock module for myapp
myapp_module = types.ModuleType('myapp')
myapp_module.__file__ = '/tmp/myapp/__init__.py' # Fake path
sys.modules['myapp'] = myapp_module

# We need to tell Django where to find the models. 
# Usually, Django scans the 'models' submodule or looks for models in __init__.
# Let's put the model in myapp.models

models_module = types.ModuleType('myapp.models')
models_module.__file__ = '/tmp/myapp/models.py'
sys.modules['myapp.models'] = models_module

# Attach the model to the module so Django's app loader finds it
models_module.CustomUser = CustomUser
models_module.models = models # import django.db.models as models inside the module scope if needed

# Update the CustomUser to point to the right module for app_label resolution
CustomUser.__module__ = 'myapp.models'

# Now we need to make sure Django's app registry picks this up.
# Since we already called django.setup(), the registry is populated.
# Adding modules to sys.modules AFTER setup won't automatically register the app.

# Alternative: Don't use django.setup() with INSTALLED_APPS containing 'myapp'.
# Instead, configure settings without 'myapp', then manually handle the check?
# No, check_user_model relies on getting the user model from settings.AUTH_USER_MODEL.

# Let's restart the configuration strategy.
# 1. Configure settings.
# 2. Define model in a way that Django can load it.
# 3. Set AUTH_USER_MODEL.
# 4. Call django.setup().
# 5. Run checks.

# Since we cannot create files, we can use an existing app in INSTALLED_APPS 
# to host our model? No, that modifies the repo state conceptually or is messy.

# Better approach: Use `django.test.utils.override_settings` or similar?
# Or simply patch the check function? No, we want to test the behavior.

# Let's look at `django.contrib.auth.checks.check_user_model`.
# It gets the user model via `apps.get_model(settings.AUTH_USER_MODEL)`.

# If we define the model in `__main__`, its app_label is `__main__`? 
# No, AbstractBaseUser doesn't set app_label. 
# We set `app_label = 'myapp'` in Meta.

# Let's try to force the app registry to include 'myapp'.
# This is hard without a proper AppConfig.

# Let's try a different tactic: 
# Directly inspect the source code of the installed Django version to see if 
# the fix is present? No, "Exercise the behaviour".

# Let's try to use `django.db.models.signals` or similar to inject the model?

# Actually, there is a simpler way. 
# The check `check_user_model` is registered in `django.contrib.auth.apps.AuthConfig.ready`.
# It checks the model referenced by `settings.AUTH_USER_MODEL`.

# If we set `AUTH_USER_MODEL` to a model that Django can't find, it fails.

# Let's create a minimal AppConfig in memory.
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = 'myapp'
    label = 'myapp'
    
    def ready(self):
        # Register the model
        from django.db import models
        # We need to ensure the model is associated with this app.
        # When we defined CustomUser, we set app_label = 'myapp'.
        # Django uses app_label to find the app config.
        pass

# Register the app config
from django.apps import apps
apps.app_configs['myapp'] = MyAppConfig('myapp', apps)
apps.all_models['myapp'] = {'customuser': CustomUser}

# Now we need to set AUTH_USER_MODEL
settings.AUTH_USER_MODEL = 'myapp.CustomUser'

# We need to re-run setup or at least ensure the model is loaded.
# Since we manipulated internal structures, we might need to clear caches.
# But `django.setup()` was already called.

# Let's try to run the check now.
from django.core.checks import registry

# Clear previous checks?
# registry.registered_checks.clear() # Dangerous

# Just run the specific tag
from django.core.management import call_command
from io import StringIO

try:
    out = StringIO()
    # Run checks for auth
    from django.core.checks import run_checks
    from django.conf import settings
    
    # Ensure tags are available
    errors = run_checks(tags=['models'])
    
    # Filter for auth.E003
    e003_errors = [e for e in errors if e.id == 'auth.E003']
    
    # If the fix is present, e003_errors should be empty because 
    # our model has a UniqueConstraint.
    # If the fix is NOT present, e003_errors will contain the error.
    
    assert len(e003_errors) == 0, f"Expected no auth.E003 errors, but got: {e003_errors}"
    
    print("Check passed: auth.E003 was correctly skipped due to UniqueConstraint.")
    sys.exit(0)

except Exception as e:
    print(f"Check failed: {e}")
    sys.exit(1)
