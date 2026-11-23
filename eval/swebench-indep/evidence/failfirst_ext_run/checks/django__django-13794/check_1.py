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

from django.template import Context, Template
from django.utils.translation import gettext_lazy as _

def test_add_filter_with_lazy_string():
    """
    Test that the 'add' template filter can concatenate a string with a lazy string.
    
    The issue reports that:
    add filter is unable to concatenate strings with lazy string
    Result is always empty string because of TypeError: can only concatenate str (not "__proxy__") to str
    
    If fixed, concatenating "Hello " with a lazy string "World" should produce "Hello World".
    """
    # Create a lazy string
    lazy_str = _("World")
    
    # Use the add filter in a template: {{ value|add:text }}
    # We want to test: "Hello " + lazy_str
    template = Template('{{ greeting|add:name }}')
    
    context = Context({
        'greeting': 'Hello ',
        'name': lazy_str,
    })
    
    result = template.render(context)
    
    # The expected result if the bug is fixed is "Hello World"
    # If the bug exists, it might be "" or raise an exception
    expected = "Hello World"
    
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
        print(f"Test error: {type(e).__name__}: {e}")
        sys.exit(1)
