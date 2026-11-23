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

from django.forms.widgets import FileInput, ClearableFileInput

def test_file_input_required_attribute():
    """
    Test that FileInput.use_required_attribute returns False when initial value is provided.
    
    The issue states that FileInput shouldn't display the required attribute when initial data exists.
    This is because if a file is already uploaded (initial data), the field shouldn't be required
    to upload a new file.
    """
    
    # Create a FileInput widget
    widget = FileInput()
    
    # Test 1: When no initial value is provided, use_required_attribute should return True
    # (assuming the field is required)
    result_no_initial = widget.use_required_attribute(initial=None)
    assert result_no_initial is True, f"Expected True when no initial value, got {result_no_initial}"
    
    # Test 2: When initial value is provided, use_required_attribute should return False
    # This is the core of the bug fix - if there's already a file, we shouldn't require a new one
    result_with_initial = widget.use_required_attribute(initial={'name': 'existing_file.txt'})
    assert result_with_initial is False, f"Expected False when initial value exists, got {result_with_initial}"
    
    # Also test with a simple string initial value (common case)
    result_with_string_initial = widget.use_required_attribute(initial='existing_file.txt')
    assert result_with_string_initial is False, f"Expected False when string initial value exists, got {result_with_string_initial}"

def test_clearable_file_input_still_works():
    """
    Ensure ClearableFileInput still behaves correctly after the change.
    """
    widget = ClearableFileInput()
    
    # When no initial value, should require attribute
    result_no_initial = widget.use_required_attribute(initial=None)
    assert result_no_initial is True, f"ClearableFileInput: Expected True when no initial value, got {result_no_initial}"
    
    # When initial value exists, should not require attribute
    result_with_initial = widget.use_required_attribute(initial={'name': 'existing_file.txt'})
    assert result_with_initial is False, f"ClearableFileInput: Expected False when initial value exists, got {result_with_initial}"

if __name__ == '__main__':
    try:
        test_file_input_required_attribute()
        test_clearable_file_input_still_works()
        print("All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
