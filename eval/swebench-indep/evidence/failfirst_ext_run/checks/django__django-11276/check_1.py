import sys
import os

# Configure Django settings minimally before importing django modules
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

def main():
    # The issue states that django.utils.html.escape() should use Python's stdlib html.escape().
    # Key points from the issue:
    # 1. It should delegate to or behave identically to stdlib html.escape for standard cases.
    # 2. A specific mention is made about single quotes: stdlib html.escape converts ' to &#x27; 
    #    whereas older Django might have used &#39;. The issue accepts this change as functionally equivalent.
    # 3. The goal is to remove duplication and use the stdlib version.
    
    # Test strings
    test_cases = [
        "<script>alert('xss')</script>",
        "Hello & Welcome",
        '"Quoted"',
        "It's a test",
        "<a href='#'>Link</a>",
        "",
        "No special chars",
    ]
    
    for text in test_cases:
        django_result = escape(text)
        stdlib_result = stdlib_html.escape(text, quote=True)
        
        # The issue implies that after the fix, django's escape should match stdlib's behavior.
        # Note: django.utils.html.escape by default escapes quotes too (quote=True equivalent).
        # Let's verify they are identical.
        
        if django_result != stdlib_result:
            print(f"Mismatch for input: {repr(text)}")
            print(f"Django result : {repr(django_result)}")
            print(f"Stdlib result : {repr(stdlib_result)}")
            raise AssertionError(f"django.utils.html.escape() does not match stdlib html.escape() for input {repr(text)}")

    # Specific check mentioned in the issue: single quote handling
    # Stdlib uses &#x27;
    text_with_quote = "It's"
    django_res = escape(text_with_quote)
    stdlib_res = stdlib_html.escape(text_with_quote, quote=True)
    
    assert '&#x27;' in django_res, "Django escape should use &#x27; for single quotes like stdlib"
    assert django_res == stdlib_res, f"Results differ: {django_res} vs {stdlib_res}"

    print("All checks passed. django.utils.html.escape() correctly delegates to/matches stdlib html.escape().")
    sys.exit(0)

if __name__ == '__main__':
    main()
