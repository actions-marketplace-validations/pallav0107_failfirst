import sys
import os

# Configure Django settings minimally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

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

def main():
    # The issue states that django.utils.html.escape should use stdlib html.escape.
    # Key behavioral differences/expectations:
    # 1. It should handle &, <, >, ", and ' correctly.
    # 2. The issue mentions a specific change in quote escaping: 
    #    stdlib html.escape converts ' to &#x27; whereas old Django used &#39;.
    #    Since Python 3.6+, stdlib html.escape defaults quote=True which escapes '.
    #    However, Django's escape function traditionally did NOT escape single quotes 
    #    unless explicitly asked or depending on version specifics.
    #    
    # Let's look at the actual behavior expected after the fix.
    # The issue says "Use Python stdlib html.escape()".
    # stdlib html.escape(s, quote=True) is the default.
    # It escapes: & -> &amp;, < -> &lt;, > -> &gt;, " -> &quot;, ' -> &#x27;
    #
    # Django's escape() usually escapes: & -> &amp;, < -> &lt;, > -> &gt;, " -> &quot;
    # Historically, Django's escape did NOT escape single quotes by default in some versions,
    # or used &#39;.
    #
    # If the fix is applied, django.utils.html.escape should behave like stdlib html.escape.
    # Specifically, the issue notes: "html.escape() converts ' to &#x27 rather than &#39".
    # This implies the new behavior SHOULD produce &#x27 for single quotes if it escapes them.
    #
    # However, we must check what Django's escape signature looks like.
    # In Django 3.0, django.utils.html.escape(text) calls conditional_escape which eventually
    # calls the internal _escape_impl.
    #
    # If the patch is applied, it likely delegates to html.escape.
    # Let's test a string with a single quote.
    
    test_string = "It's a test"
    
    # Standard library behavior (default quote=True)
    stdlib_result = stdlib_html.escape(test_string)
    
    # Django's result
    django_result = escape(test_string)
    
    # According to the issue, the fix makes Django use stdlib html.escape.
    # Therefore, the results should match.
    # Note: stdlib_html.escape escapes ' to &#x27;
    
    print(f"Input: {test_string}")
    print(f"Stdlib result: {stdlib_result}")
    print(f"Django result: {django_result}")
    
    # Assert that they are equal
    assert django_result == stdlib_result, f"Mismatch: Django produced '{django_result}' but stdlib produced '{stdlib_result}'"
    
    # Also test other characters to ensure full compliance
    test_string_2 = '<div class="test">Hello & World</div>'
    stdlib_result_2 = stdlib_html.escape(test_string_2)
    django_result_2 = escape(test_string_2)
    
    print(f"Input: {test_string_2}")
    print(f"Stdlib result: {stdlib_result_2}")
    print(f"Django result: {django_result_2}")
    
    assert django_result_2 == stdlib_result_2, f"Mismatch: Django produced '{django_result_2}' but stdlib produced '{stdlib_result_2}'"

    sys.exit(0)

if __name__ == '__main__':
    main()
