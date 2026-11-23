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
    
    # Use the add filter in a template: {{ value|add:"Hello " }}
    # We want to test adding a regular string to a lazy string
    # The template syntax is {{ lazy_value|add:"prefix " }} which translates to "prefix " + lazy_value
    
    template = Template('{{ value|add:"Hello " }}')
    context = Context({'value': lazy_str})
    result = template.render(context)
    
    # If the bug exists, result will be empty string '' due to exception being swallowed
    # If fixed, result should be "Hello World" (or translated version of World)
    
    # Let's also test the other direction: {{ "Hello "|add:value }}
    template2 = Template('{{ "Hello "|add:value }}')
    context2 = Context({'value': lazy_str})
    result2 = template2.render(context2)
    
    # At least one of these should work correctly if the fix is in place
    # The expected result contains "Hello " and the lazy string value
    
    # Force evaluation of lazy string to get its actual value for comparison
    lazy_str_evaluated = str(lazy_str)
    
    expected1 = "Hello " + lazy_str_evaluated
    expected2 = "Hello " + lazy_str_evaluated
    
    # Check that results are not empty (which would indicate the bug)
    assert result != "", f"Result was empty string, indicating the bug still exists. Got: '{result}'"
    assert result2 != "", f"Result2 was empty string, indicating the bug still exists. Got: '{result2}'"
    
    # Check that the results contain the expected parts
    assert "Hello " in result, f"Expected 'Hello ' in result, got: '{result}'"
    assert lazy_str_evaluated in result, f"Expected '{lazy_str_evaluated}' in result, got: '{result}'"
    
    assert "Hello " in result2, f"Expected 'Hello ' in result2, got: '{result2}'"
    assert lazy_str_evaluated in result2, f"Expected '{lazy_str_evaluated}' in result2, got: '{result2}'"

if __name__ == '__main__':
    try:
        test_add_filter_with_lazy_string()
        print("Test passed: The add filter correctly handles lazy strings.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
