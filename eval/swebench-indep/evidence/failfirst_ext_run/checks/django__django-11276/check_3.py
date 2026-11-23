import sys
import os

# Configure Django settings minimally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-only',
    )

django.setup()

from django.utils.html import escape
import html as stdlib_html

def check_escape_behavior():
    """
    Check if django.utils.html.escape uses stdlib html.escape behavior.
    
    The issue states that django.utils.html.escape should be replaced by 
    stdlib html.escape for performance and maintenance reasons.
    
    Key behavioral differences to check:
    1. Both should escape <, >, &, and optionally quotes
    2. The issue mentions that stdlib html.escape converts ' to &#x27 
       while Django's old implementation used &#39. These are functionally 
       equivalent but the literal text changes.
    3. After the fix, django.utils.html.escape should behave identically 
       to stdlib html.escape (with quote=True by default in stdlib, but 
       Django's escape typically doesn't escape quotes by default).
       
    Let's check the actual behavior of both functions.
    """
    
    # Test basic escaping
    test_string = "<script>alert('xss')</script>"
    
    django_result = escape(test_string)
    stdlib_result = stdlib_html.escape(test_string, quote=False)
    
    # Django's escape by default does not escape quotes, similar to 
    # stdlib html.escape with quote=False
    
    # After the fix, they should produce identical output
    assert django_result == stdlib_result, (
        f"django.utils.html.escape produced: {django_result!r}\n"
        f"stdlib html.escape (quote=False) produced: {stdlib_result!r}\n"
        "They should be identical after the fix."
    )
    
    # Test with ampersand
    test_amp = "Tom & Jerry"
    django_amp = escape(test_amp)
    stdlib_amp = stdlib_html.escape(test_amp, quote=False)
    assert django_amp == stdlib_amp, (
        f"Ampersand test failed: django={django_amp!r}, stdlib={stdlib_amp!r}"
    )
    
    # Test with less than and greater than
    test_brackets = "a < b > c"
    django_brackets = escape(test_brackets)
    stdlib_brackets = stdlib_html.escape(test_brackets, quote=False)
    assert django_brackets == stdlib_brackets, (
        f"Brackets test failed: django={django_brackets!r}, stdlib={stdlib_brackets!r}"
    )
    
    # Test empty string
    assert escape("") == stdlib_html.escape("", quote=False)
    
    # Test string with no special characters
    assert escape("hello world") == stdlib_html.escape("hello world", quote=False)
    
    # Test the specific mention about single quotes
    # The issue says html.escape converts ' to &#x27 
    # Let's verify what stdlib does with quote=True vs quote=False
    test_quote = "It's a test"
    stdlib_no_quote = stdlib_html.escape(test_quote, quote=False)
    stdlib_with_quote = stdlib_html.escape(test_quote, quote=True)
    
    # Django's escape traditionally does NOT escape quotes
    # So it should match stdlib with quote=False
    django_quote = escape(test_quote)
    assert django_quote == stdlib_no_quote, (
        f"Quote test failed: django={django_quote!r}, stdlib(no quote)={stdlib_no_quote!r}"
    )
    
    # Verify that the single quote is NOT escaped in django's output
    # (matching stdlib quote=False behavior)
    assert "&#39;" not in django_quote or "'" in django_quote, (
        "Django escape should not escape single quotes by default"
    )
    
    print("All checks passed: django.utils.html.escape behaves like stdlib html.escape")

if __name__ == "__main__":
    try:
        check_escape_behavior()
        sys.exit(0)
    except AssertionError as e:
        print(f"Check failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
