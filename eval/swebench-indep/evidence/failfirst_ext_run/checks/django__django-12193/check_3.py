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
    Test that SplitArrayField with BooleanField correctly renders checkboxes
    based on their individual values, not sharing state after the first True.
    """
    
    # Create a form class with a SplitArrayField containing BooleanFields
    class TestForm(forms.Form):
        # We need an initial data array like [True, False, True]
        # The bug is that after the first True, all subsequent widgets 
        # get 'checked': True in their attrs because the dict is mutated.
        my_field = SplitArrayField(forms.BooleanField(), size=3)

    # Initial data where the second value is False
    initial_data = {
        'my_field_0': True,
        'my_field_1': False,
        'my_field_2': True,
    }
    
    # Create the form with initial data
    form = TestForm(initial=initial_data)
    
    # Render the form to trigger widget rendering
    html = str(form)
    
    # We need to check the context or the rendered HTML for each checkbox.
    # A more direct way is to inspect the widgets' get_context output or 
    # the subwidgets directly if possible. However, SplitArrayField uses 
    # SubWidget iteration.
    
    # Let's look at the field's widget and how it renders subwidgets.
    field = form.fields['my_field']
    widget = field.widget
    
    # The widget is a SplitArrayWidget. It creates subwidgets.
    # We can iterate over the subwidgets and check their checked state.
    
    # Get the value from initial data for the field
    # The form's initial data is passed to the field.
    
    # Let's render the field specifically and parse the HTML or check contexts.
    # Actually, let's look at the internal behavior.
    
    # The issue states that CheckboxInput modifies the attrs dict.
    # Let's simulate what happens during rendering.
    
    # Prepare the value as the field would see it
    value = [True, False, True]
    
    # Get the subwidgets
    # SplitArrayWidget has a method to get subwidgets? 
    # In Django 3.1, SplitArrayWidget.render creates subwidgets.
    
    # Let's use the form's bound field to get the widget rendering context
    bound_field = form['my_field']
    
    # The widget is SplitArrayWidget. Let's look at its subwidgets.
    # We can access the subwidgets via the widget's __iter__ or by rendering.
    
    # A robust way: Check the rendered HTML for "checked" attribute presence.
    # Index 0: True -> should be checked
    # Index 1: False -> should NOT be checked
    # Index 2: True -> should be checked
    
    # Parse the HTML for each checkbox input.
    # The names will be my_field_0, my_field_1, my_field_2
    
    import re
    
    # Find all checkbox inputs for my_field
    # Pattern for input type="checkbox" name="my_field_X"
    checkboxes = []
    for i in range(3):
        pattern = rf'<input[^>]*name="my_field_{i}"[^>]*>'
        match = re.search(pattern, html)
        assert match, f"Checkbox for my_field_{i} not found in HTML"
        checkboxes.append(match.group(0))
    
    # Check index 0: Should be checked
    cb0 = checkboxes[0]
    assert 'checked' in cb0, f"Checkbox 0 (True) should be checked. HTML: {cb0}"
    
    # Check index 1: Should NOT be checked (this is the bug case)
    cb1 = checkboxes[1]
    assert 'checked' not in cb1, f"Checkbox 1 (False) should NOT be checked. HTML: {cb1}"
    
    # Check index 2: Should be checked
    cb2 = checkboxes[2]
    assert 'checked' in cb2, f"Checkbox 2 (True) should be checked. HTML: {cb2}"

if __name__ == '__main__':
    try:
        test_split_array_boolean_field()
        print("Test passed: Behavior is correct.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
