import os
import sys

# Configure Django settings before importing anything else from Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-script-only',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )

django.setup()

from django.utils.translation import gettext_lazy as _
from django.template import Template, Context


def test_add_filter_with_lazy_string():
    """
    Test that the 'add' template filter can concatenate a string with a lazy string.
    
    The issue reports that using the add filter to concatenate a string with a lazy string
    results in an empty string due to a TypeError.
    
    If the bug is fixed, the concatenation should work correctly.
    """
    # Create a lazy string
    lazy_str = _("Hello")
    
    # Create a template that uses the add filter to concatenate a string with the lazy string
    # We'll pass the lazy string as part of the context and try to add a normal string to it
    template = Template("{{ value|add:' World' }}")
    
    # Render the template with the lazy string
    context = Context({'value': lazy_str})
    result = template.render(context)
    
    # The expected result is "Hello World"
    expected = "Hello World"
    
    # Assert that the result matches the expected output
    assert result == expected, f"Expected '{expected}', but got '{result}'"


if __name__ == '__main__':
    try:
        test_add_filter_with_lazy_string()
        print("Test passed: The add filter correctly concatenates strings with lazy strings.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
