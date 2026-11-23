import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-only',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'OPTIONS': {
                'builtins': ['django.template.defaultfilters'],
            },
        }],
    )

django.setup()

from django.template import Template, Context

def test_escapeseq_filter():
    """
    Test the new `escapeseq` template filter.
    
    The issue requests a filter that escapes each item in a list,
    similar to how `safeseq` marks them as safe. This is useful when
    autoescape is off and we want to manually escape items before joining.
    
    Example usage from issue: {{ some_list|escapeseq|join:"," }}
    """
    
    # Test 1: Basic escaping with autoescape off
    # If autoescape is off, <script> should remain <script> unless explicitly escaped.
    # escapeseq should escape each element.
    template_str = "{% autoescape off %}{{ items|escapeseq|join:\",\" }}{% endautoescape %}"
    template = Template(template_str)
    
    context = Context({
        'items': ['<b>bold</b>', '<script>alert(1)</script>', 'normal']
    })
    
    result = template.render(context)
    
    # Expected: Each item should be HTML escaped
    # <b>bold</b> -> &lt;b&gt;bold&lt;/b&gt;
    # <script>alert(1)</script> -> &lt;script&gt;alert(1)&lt;/script&gt;
    # normal -> normal
    
    expected = "&lt;b&gt;bold&lt;/b&gt;,&lt;script&gt;alert(1)&lt;/script&gt;,normal"
    
    assert result == expected, f"Expected '{expected}', got '{result}'"
    
    # Test 2: Empty list
    template_str_empty = "{% autoescape off %}{{ items|escapeseq|join:\",\" }}{% endautoescape %}"
    template_empty = Template(template_str_empty)
    context_empty = Context({'items': []})
    result_empty = template_empty.render(context_empty)
    assert result_empty == "", f"Expected empty string for empty list, got '{result_empty}'"
    
    # Test 3: List with safe strings (should still be escaped by escapeseq)
    # safeseq marks items as safe, escapeseq should escape them regardless
    from django.utils.safestring import mark_safe
    template_str_safe = "{% autoescape off %}{{ items|escapeseq|join:\",\" }}{% endautoescape %}"
    template_safe = Template(template_str_safe)
    context_safe = Context({
        'items': [mark_safe('<b>safe</b>'), 'regular']
    })
    result_safe = template_safe.render(context_safe)
    # escapeseq should escape even safe strings because its purpose is to escape
    expected_safe = "&lt;b&gt;safe&lt;/b&gt;,regular"
    assert result_safe == expected_safe, f"Expected '{expected_safe}', got '{result_safe}'"

    # Test 4: Verify the filter exists and is callable
    from django.template.defaultfilters import escapeseq
    assert callable(escapeseq), "escapeseq should be callable"
    
    # Direct function test
    test_list = ['<a>', '<b>']
    escaped = escapeseq(test_list)
    # The filter returns a list of SafeString objects that are escaped
    assert len(escaped) == 2
    assert str(escaped[0]) == '&lt;a&gt;'
    assert str(escaped[1]) == '&lt;b&gt;'

if __name__ == '__main__':
    try:
        test_escapeseq_filter()
        print("All tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
