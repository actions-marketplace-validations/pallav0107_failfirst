import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
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
        ],
        SECRET_KEY='test-secret-key-for-check-script-only',
    )

django.setup()

from django.contrib.auth.forms import AuthenticationForm

def check_maxlength_attribute():
    """
    Check if the username field in AuthenticationForm has the maxlength HTML attribute.
    
    The issue states that AuthenticationForm's username field doesn't render with 
    maxlength HTML attribute anymore due to a regression.
    
    We need to verify that the rendered widget for the username field includes 
    the maxlength attribute.
    """
    form = AuthenticationForm()
    
    # Get the username field
    username_field = form.fields['username']
    
    # Render the widget to get the HTML
    html_output = str(username_field.widget.render('username', ''))
    
    # Check if maxlength attribute is present in the rendered HTML
    assert 'maxlength' in html_output, f"maxlength attribute not found in rendered username field HTML: {html_output}"
    
    # Additionally, we can check the widget attributes directly if available
    # The username field should have a max_length defined
    assert hasattr(username_field, 'max_length'), "Username field should have max_length attribute"
    assert username_field.max_length is not None, "Username field max_length should not be None"
    
    # Verify the maxlength value matches the field's max_length
    expected_maxlength = f'maxlength="{username_field.max_length}"'
    assert expected_maxlength in html_output, f"Expected '{expected_maxlength}' not found in HTML: {html_output}"

if __name__ == '__main__':
    try:
        check_maxlength_attribute()
        print("PASS: AuthenticationForm username field correctly includes maxlength attribute.")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error occurred: {e}")
        sys.exit(2)
