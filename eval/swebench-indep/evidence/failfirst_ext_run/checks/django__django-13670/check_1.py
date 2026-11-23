import sys
import os

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-script-only',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )
    django.setup()

import datetime
from django.utils import dateformat

def main():
    # The issue states that for a year like 123, format "y" returns '3' instead of '23'.
    # Python's strftime and PHP return the last two digits with leading zero if necessary.
    # Year 123 -> last two digits are 23.
    
    test_date = datetime.datetime(123, 4, 5, 6, 7)
    
    # Get the result from Django's dateformat
    result = dateformat.format(test_date, "y")
    
    # Expected behavior: consistent with Python's strftime("%y") which returns '23'
    expected = "23"
    
    # Assert that the result matches the expected behavior
    assert result == expected, f"Expected '{expected}', but got '{result}'"
    
    # Additional check for year < 10 (e.g., year 5 should be '05')
    test_date_2 = datetime.datetime(5, 1, 1)
    result_2 = dateformat.format(test_date_2, "y")
    expected_2 = "05"
    assert result_2 == expected_2, f"Expected '{expected_2}', but got '{result_2}'"

    # Additional check for year between 10 and 99 (e.g., year 99 should be '99')
    test_date_3 = datetime.datetime(99, 1, 1)
    result_3 = dateformat.format(test_date_3, "y")
    expected_3 = "99"
    assert result_3 == expected_3, f"Expected '{expected_3}', but got '{result_3}'"

    # Additional check for year 1000 (should be '00')
    test_date_4 = datetime.datetime(1000, 1, 1)
    result_4 = dateformat.format(test_date_4, "y")
    expected_4 = "00"
    assert result_4 == expected_4, f"Expected '{expected_4}', but got '{result_4}'"

    sys.exit(0)

if __name__ == '__main__':
    main()
