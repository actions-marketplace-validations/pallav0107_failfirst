import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

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
        USE_TZ=True,
    )

django.setup()

from django.forms.widgets import FileInput, ClearableFileInput


def test_file_input_required_attribute_with_initial():
    """
    Test that FileInput does not render the 'required' attribute when initial data exists.
    
    The issue states that FileInput.use_required_attribute() should return False 
    when there is initial data (a file already set), similar to how ClearableFileInput behaves.
    """
    
    # Create a FileInput widget
    widget = FileInput()
    
    # Test 1: When value is None (no initial data), required attribute should be allowed
    # use_required_attribute returns True if the field is required and no initial value
    # We pass value=None to simulate no initial file
    result_no_initial = widget.use_required_attribute(None)
    assert result_no_initial is True, "FileInput should allow required attribute when no initial data"
    
    # Test 2: When value exists (initial data present), required attribute should NOT be rendered
    # Pass a non-None value to simulate an existing file
    result_with_initial = widget.use_required_attribute("some_existing_file.txt")
    
    # According to the issue, this should return False so that 'required' is not output
    # when a file is already set
    assert result_with_initial is False, (
        f"FileInput.use_required_attribute() should return False when initial data exists, "
        f"but got {result_with_initial}"
    )


def test_clearable_file_input_behavior():
    """
    Verify that ClearableFileInput already has the correct behavior for comparison.
    """
    widget = ClearableFileInput()
    
    # With no initial value, required should be allowed
    result_no_initial = widget.use_required_attribute(None)
    assert result_no_initial is True, "ClearableFileInput should allow required attribute when no initial data"
    
    # With initial value, required should not be allowed
    result_with_initial = widget.use_required_attribute("some_existing_file.txt")
    assert result_with_initial is False, (
        f"ClearableFileInput.use_required_attribute() should return False when initial data exists, "
        f"but got {result_with_initial}"
    )


if __name__ == '__main__':
    try:
        test_clearable_file_input_behavior()
        test_file_input_required_attribute_with_initial()
        print("All tests passed. The issue is fixed.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
