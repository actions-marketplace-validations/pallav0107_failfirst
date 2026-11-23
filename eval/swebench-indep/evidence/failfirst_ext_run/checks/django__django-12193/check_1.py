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
        SECRET_KEY='test-secret-key-for-check-script-only',
    )

django.setup()

from django import forms
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.forms import SplitArrayField
from django.forms.widgets import CheckboxInput


class TestForm(forms.Form):
    # We use SplitArrayField with a base field of BooleanField.
    # Note: In Django 3.1, SplitArrayField is in django.contrib.postgres.forms.
    # It requires a base_field and size.
    my_array = SplitArrayField(base_field=forms.BooleanField(), size=3)


def main():
    # Create a form instance with initial data where the first value is True,
    # but subsequent values are False.
    # According to the bug report, if the first value is True, the widget attrs
    # are modified in place, causing subsequent widgets to also appear checked.
    
    initial_data = {
        'my_array': [True, False, False]
    }
    
    form = TestForm(initial=initial_data)
    
    # Render the form to trigger widget rendering
    html = form.as_p()
    
    # We need to check if the rendered HTML correctly reflects the initial data.
    # The first checkbox should be checked.
    # The second and third checkboxes should NOT be checked.
    
    # Let's parse the rendered HTML or check the widget contexts directly.
    # Checking the widget contexts is more direct and less brittle than parsing HTML.
    
    # Get the field
    field = form.fields['my_array']
    
    # The SplitArrayField creates sub-widgets. We need to access them.
    # In Django, SplitArrayField uses a custom widget that renders multiple sub-widgets.
    # Let's look at how the widgets are rendered.
    
    # Actually, let's look at the rendered HTML string for simplicity and robustness.
    # The CheckboxInput renders an <input type="checkbox" ...>.
    # If 'checked' is present, it's checked.
    
    # Split the HTML by checkbox inputs to analyze each one.
    # This is a bit fragile, but let's try to find the checkboxes.
    
    # A better approach: inspect the sub-widgets' get_context output if possible,
    # or just rely on the HTML output which is the user-facing behavior.
    
    # Let's count how many times 'checked' appears in the HTML for the checkboxes.
    # We expect exactly one 'checked' attribute (for the first item).
    
    # However, 'checked' might appear in other contexts? Unlikely in this simple form.
    # Let's be more precise.
    
    # The SplitArrayField widget renders inputs with names like my_array_0, my_array_1, etc.
    
    import re
    
    # Find all checkbox inputs for my_array
    # Pattern matches <input ... type="checkbox" ... name="my_array_N" ...>
    # We want to see if they have the 'checked' attribute.
    
    # Extract the three checkbox inputs
    checkboxes = []
    for i in range(3):
        # Look for the input tag for my_array_i
        pattern = rf'<input[^>]*name="my_array_{i}"[^>]*>'
        match = re.search(pattern, html)
        if match:
            checkboxes.append(match.group(0))
        else:
            raise AssertionError(f"Could not find checkbox for my_array_{i} in rendered HTML")
    
    # Check each checkbox
    # First one should be checked
    assert 'checked' in checkboxes[0], f"First checkbox should be checked, but got: {checkboxes[0]}"
    
    # Second one should NOT be checked
    assert 'checked' not in checkboxes[1], f"Second checkbox should NOT be checked, but got: {checkboxes[1]}"
    
    # Third one should NOT be checked
    assert 'checked' not in checkboxes[2], f"Third checkbox should NOT be checked, but got: {checkboxes[2]}"
    
    print("All checks passed. The bug is fixed.")
    sys.exit(0)


if __name__ == '__main__':
    main()
