import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

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
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [],
            },
        }],
    )

django.setup()

from django.template import Template, Context

def test_escapeseq_filter():
    """
    Test the new 'escapeseq' template filter.
    
    The issue requests a filter that escapes each item in a sequence,
    similar to how 'safeseq' marks items as safe. This is useful when
    autoescape is off and you want to join escaped items.
    
    Example usage from issue: {{ some_list|escapeseq|join:"," }}
    """
    
    # Test 1: Basic functionality with autoescape off
    # When autoescape is off, HTML entities should be escaped by escapeseq
    template_str = "{% autoescape off %}{{ some_list|escapeseq|join:',' }}{% endautoescape %}"
    template = Template(template_str)
    
    # List containing HTML special characters
    context_data = {
        'some_list': ['<b>bold</b>', '<i>italic</i>', 'normal']
    }
    context = Context(context_data)
    
    result = template.render(context)
    
    # Each item should be HTML-escaped
    # <b>bold</b> should become &lt;b&gt;bold&lt;/b&gt;
    # <i>italic</i> should become &lt;i&gt;italic&lt;/i&gt;
    # normal should remain normal
    expected = "&lt;b&gt;bold&lt;/b&gt;,&lt;i&gt;italic&lt;/i&gt;,normal"
    
    assert result == expected, f"Expected '{expected}', but got '{result}'"
    
    # Test 2: Empty list
    template_str_empty = "{% autoescape off %}{{ empty_list|escapeseq|join:',' }}{% endautoescape %}"
    template_empty = Template(template_str_empty)
    context_empty = Context({'empty_list': []})
    result_empty = template_empty.render(context_empty)
    assert result_empty == "", f"Expected empty string for empty list, but got '{result_empty}'"
    
    # Test 3: Single item
    template_str_single = "{% autoescape off %}{{ single_list|escapeseq|join:',' }}{% endautoescape %}"
    template_single = Template(template_str_single)
    context_single = Context({'single_list': ['<script>alert("xss")</script>']})
    result_single = template_single.render(context_single)
    expected_single = "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
    assert result_single == expected_single, f"Expected '{expected_single}', but got '{result_single}'"
    
    # Test 4: With different separator
    template_str_sep = "{% autoescape off %}{{ items|escapeseq|join:' | ' }}{% endautoescape %}"
    template_sep = Template(template_str_sep)
    context_sep = Context({'items': ['a&b', 'c<d']})
    result_sep = template_sep.render(context_sep)
    expected_sep = "a&amp;b | c&lt;d"
    assert result_sep == expected_sep, f"Expected '{expected_sep}', but got '{result_sep}'"
    
    # Test 5: Verify it works with autoescape on (should double-escape or just escape once depending on implementation)
    # When autoescape is ON, the output of escapeseq might be marked safe or not.
    # Let's check that it doesn't break anything.
    template_str_auto_on = "{{ some_list|escapeseq|join:',' }}"
    template_auto_on = Template(template_str_auto_on)
    context_auto_on = Context({'some_list': ['<b>test</b>']})
    result_auto_on = template_auto_on.render(context_auto_on)
    # With autoescape on, the joined string will be escaped again if escapeseq doesn't mark as safe
    # Or if escapeseq returns safe strings, they won't be double-escaped.
    # The key point is that escapeseq should escape the individual items.
    # If autoescape is on, and escapeseq returns escaped but NOT safe strings, then:
    # '<b>test</b>' -> '&lt;b&gt;test&lt;/b&gt;' by escapeseq
    # Then join produces '&lt;b&gt;test&lt;/b&gt;'
    # Then autoescape escapes it again: '&amp;lt;b&amp;gt;test&amp;lt;/b&amp;gt;'
    # If escapeseq returns SAFE strings (like safeseq does), then no double escaping.
    # Based on the analogy with safeseq, escapeseq likely returns safe strings after escaping.
    # Let's assume it returns safe strings so no double escaping occurs.
    expected_auto_on = "&lt;b&gt;test&lt;/b&gt;"
    assert result_auto_on == expected_auto_on, f"Expected '{expected_auto_on}', but got '{result_auto_on}'"

if __name__ == '__main__':
    try:
        test_escapeseq_filter()
        print("All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during testing: {e}")
        sys.exit(1)
