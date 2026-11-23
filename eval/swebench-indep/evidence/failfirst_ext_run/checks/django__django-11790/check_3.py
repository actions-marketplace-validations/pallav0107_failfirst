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
    Check if the username field in AuthenticationForm has the maxlength HTML attribute.
    
    The issue states that AuthenticationForm's username field doesn't render with 
    maxlength HTML attribute anymore due to a regression.
    
    We need to verify that the username field widget has maxlength set correctly.
    """
    form = AuthenticationForm()
    username_field = form.fields['username']
    widget = username_field.widget
    
    # Get the attributes that will be rendered in HTML
    attrs = widget.attrs
    
    # Check if maxlength is present in the widget attributes
    assert 'maxlength' in attrs, "The username field widget does not have 'maxlength' in its attributes"
    
    # Also verify by rendering the widget to see if maxlength appears in HTML
    html_output = str(username_field)
    assert 'maxlength=' in html_output or 'maxlength =' in html_output, \
        f"The rendered username field does not contain maxlength attribute. HTML: {html_output}"
    
    # The max length should match the User model's username max_length (254 by default in Django 3.1)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    max_length = User._meta.get_field('username').max_length
    
    assert attrs.get('maxlength') == max_length, \
        f"Expected maxlength to be {max_length}, but got {attrs.get('maxlength')}"

if __name__ == '__main__':
    try:
        check_username_maxlength()
        print("PASS: AuthenticationForm's username field correctly sets maxlength HTML attribute.")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
