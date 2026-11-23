import os
import sys

# Configure Django settings minimally
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
                'context_processors': [],
            },
        }],
    )

django.setup()

from django.template import Template, Context

def test_escapeseq_filter():
    """
    Test that the 'escapeseq' filter exists and works as described in the issue.
    
    The issue states:
    - New template filter `escapeseq`
    - It escapes each item in a sequence, similar to how `safeseq` marks them safe.
    - Usage example: {{ some_list|escapeseq|join:"," }}
    - This is useful when autoescape is off.
    """
    
    # Test 1: Check if the filter is registered
    from django.template.defaultfilters import escapeseq
    
    # Test 2: Basic functionality with autoescape off
    # When autoescape is off, HTML characters should be escaped by escapeseq
    template_str = "{% autoescape off %}{{ items|escapeseq|join:', ' }}{% endautoescape %}"
    template = Template(template_str)
    
    # Input with HTML special characters
    context_data = {
        'items': ['<script>', 'a&b', '"quote"']
    }
    context = Context(context_data)
    
    result = template.render(context)
    
    # Expected: Each item should be HTML-escaped
    # '<script>' -> '&lt;script&gt;'
    # 'a&b' -> 'a&amp;b'
    # '"quote"' -> '&quot;quote&quot;'
    expected = '&lt;script&gt;, a&amp;b, &quot;quote&quot;'
    
    assert result == expected, f"Expected '{expected}', but got '{result}'"
    
    # Test 3: Verify it works with empty list
    template_str_empty = "{% autoescape off %}{{ items|escapeseq|join:', ' }}{% endautoescape %}"
    template_empty = Template(template_str_empty)
    context_empty = Context({'items': []})
    result_empty = template_empty.render(context_empty)
    assert result_empty == '', f"Expected empty string for empty list, but got '{result_empty}'"
    
    # Test 4: Verify it works with single item
    template_str_single = "{% autoescape off %}{{ items|escapeseq|join:', ' }}{% endautoescape %}"
    template_single = Template(template_str_single)
    context_single = Context({'items': ['<b>bold</b>']})
    result_single = template_single.render(context_single)
    assert result_single == '&lt;b&gt;bold&lt;/b&gt;', f"Expected '&lt;b&gt;bold&lt;/b&gt;', but got '{result_single}'"

    print("All tests passed!")

if __name__ == '__main__':
    try:
        test_escapeseq_filter()
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
