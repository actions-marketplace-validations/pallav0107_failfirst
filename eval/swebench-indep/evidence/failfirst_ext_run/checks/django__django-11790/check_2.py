import os
import sys

# Configure Django settings before importing Django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-script-only',
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
        ],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
    )

django.setup()

from django.contrib.auth.forms import AuthenticationForm

def check_username_maxlength():
    """
    Check if the username field in AuthenticationForm has the maxlength attribute.
    
    The issue states that AuthenticationForm's username field doesn't render with 
    maxlength HTML attribute anymore. This was a regression.
    
    We need to verify that the username field has a maxlength attribute set.
    """
    form = AuthenticationForm()
    username_field = form.fields['username']
    
    # Check if the widget has maxlength attribute
    # In Django forms, the maxlength can be set via widget attrs or max_length parameter
    widget = username_field.widget
    
    # Get the attributes that will be rendered in HTML
    attrs = widget.attrs
    
    # The maxlength should be present in the widget's attrs
    assert 'maxlength' in attrs, "Username field widget does not have 'maxlength' in its attrs"
    
    # Also verify it has a reasonable value (typically 254 for email/username in Django)
    maxlength_value = attrs.get('maxlength')
    assert maxlength_value is not None, "maxlength attribute exists but has no value"
    
    # Convert to int if it's a string
    if isinstance(maxlength_value, str):
        maxlength_value = int(maxlength_value)
    
    # Django's User model username field has max_length=150 by default
    # But AuthenticationForm might use different validation
    # Let's just ensure it's a positive integer
    assert isinstance(maxlength_value, int) and maxlength_value > 0, \
        f"maxlength value should be a positive integer, got {maxlength_value}"

if __name__ == '__main__':
    try:
        check_username_maxlength()
        print("PASS: AuthenticationForm username field has maxlength attribute")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
