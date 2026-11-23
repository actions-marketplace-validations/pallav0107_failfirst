import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

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
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        SECRET_KEY='test-secret-key',
    )

django.setup()

from django import forms
from django.contrib.postgres.forms import SplitArrayField
from django.forms.widgets import CheckboxInput


def test_split_array_boolean_field():
    """
    Test that SplitArrayField with BooleanField correctly handles initial data
    where some values are True and some are False.
    
    The bug is that after the first True value, all subsequent widgets are checked
    even if their corresponding data value is False.
    """
    
    # Create a form field with SplitArrayField containing BooleanFields
    class TestForm(forms.Form):
        my_array = SplitArrayField(
            base_field=forms.BooleanField(),
            size=4,
            required=False,
        )
    
    # Initial data with mixed True/False values
    # Index 0: True, Index 1: False, Index 2: True, Index 3: False
    initial_data = {
        'my_array': [True, False, True, False]
    }
    
    form = TestForm(initial=initial_data)
    
    # Render the form to trigger widget rendering
    html = form.as_p()
    
    # We need to check the individual widgets' rendered state
    # Let's access the field's widget directly to inspect its behavior
    
    # Get the bound field
    bound_field = form['my_array']
    
    # The SplitArrayField uses a SplitArrayWidget which contains multiple sub-widgets
    # We need to check if each checkbox has the correct 'checked' attribute
    
    # Let's render each sub-widget individually by accessing the widget's decomposition
    widget = bound_field.field.widget
    
    # The SplitArrayWidget decomposes into multiple widgets
    # We can check the context generated for each sub-widget
    
    # Get the value from initial data
    values = initial_data['my_array']
    
    # Decompose the widget to get sub-widgets
    # In Django's SplitArrayWidget, it creates multiple instances of the base widget
    
    # Let's manually check what happens when we render each checkbox
    # by simulating what the widget does
    
    # The issue states that CheckboxInput.get_context() modifies the attrs dict
    # passed to it, causing subsequent widgets to inherit 'checked': True
    
    # Let's verify by checking the rendered HTML for each checkbox
    # The rendered HTML should contain 'checked' only for indices 0 and 2
    
    # Parse the HTML to find checkboxes
    # Simple approach: count occurrences of 'checked' in the rendered HTML
    # But we need to be more precise
    
    # Let's access the sub-widgets directly
    # SplitArrayWidget stores sub-widgets in self.widgets
    
    # Actually, let's look at how the widget renders
    # We'll use the widget's render method with specific values
    
    # Create a simple test to verify the bug
    # We'll create individual CheckboxInput widgets and see if they share state
    
    # First, let's verify the actual bug by checking the widget contexts
    from django.forms.boundfield import BoundField
    
    # Get the HTML output
    # Each checkbox should be rendered independently
    
    # Let's check if 'checked' appears exactly twice in the HTML (for indices 0 and 2)
    # This is a simplified check
    
    # Count how many times 'checked' appears in the rendered checkboxes
    # The HTML will have something like <input type="checkbox" name="..." checked>
    
    import re
    
    # Find all checkbox inputs in the HTML
    checkbox_pattern = r'<input[^>]*type=["\']checkbox["\'][^>]*>'
    checkboxes = re.findall(checkbox_pattern, html)
    
    # Count how many have 'checked' attribute
    checked_count = sum(1 for cb in checkboxes if 'checked' in cb)
    
    # We expect exactly 2 checked boxes (indices 0 and 2)
    expected_checked = 2
    
    # Assert that the number of checked boxes matches expectations
    assert checked_count == expected_checked, \
        f"Expected {expected_checked} checked checkboxes, but found {checked_checked}. " \
        f"This indicates the bug where widgets after the first True value are incorrectly checked."
    
    # More precise check: verify each individual checkbox state
    # Let's extract the name/index of each checkbox and verify its state
    
    # The checkboxes should be named like my_array_0, my_array_1, etc.
    # Let's verify each one
    
    checkbox_details = []
    for i, cb in enumerate(checkboxes):
        has_checked = 'checked' in cb
        # Extract index from name if possible
        name_match = re.search(r'name=["\']my_array_(\d+)["\']', cb)
        if name_match:
            idx = int(name_match.group(1))
            checkbox_details.append((idx, has_checked))
    
    # Sort by index
    checkbox_details.sort(key=lambda x: x[0])
    
    # Verify each checkbox matches the expected state
    for idx, is_checked in checkbox_details:
        expected = values[idx]
        assert is_checked == expected, \
            f"Checkbox at index {idx} is {'checked' if is_checked else 'unchecked'}, " \
            f"but expected {'checked' if expected else 'unchecked'} based on initial data {values}"


if __name__ == '__main__':
    try:
        test_split_array_boolean_field()
        print("Test passed: The issue has been fixed.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
