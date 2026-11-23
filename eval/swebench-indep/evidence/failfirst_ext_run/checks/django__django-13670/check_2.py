import sys
import datetime

# Configure Django settings minimally
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        USE_TZ=False,  # Simplify timezone handling for this check
        SECRET_KEY='test-secret-key-for-check-only',
    )
    django.setup()

from django.utils import dateformat

def main():
    # The issue states that dateformat.y() doesn't support years < 1000 correctly.
    # Specifically, for year 123, it returns '3' instead of '23'.
    # Python's strftime("%y") returns '23' for year 123.
    # PHP's date("y") also returns '23'.
    # Therefore, the expected behavior is a two-digit year with leading zero if necessary.
    
    test_date = datetime.datetime(123, 4, 5, 6, 7)
    
    # Get the result from Django's dateformat using the 'y' format character
    result = dateformat.format(test_date, "y")
    
    # Expected result based on Python stdlib and PHP behavior: '23'
    expected = "23"
    
    # Assert that the result matches the expected behavior
    assert result == expected, f"Expected '{expected}', but got '{result}'"
    
    # Additional check for another edge case: year 9
    test_date_2 = datetime.datetime(9, 1, 1)
    result_2 = dateformat.format(test_date_2, "y")
    expected_2 = "09"
    assert result_2 == expected_2, f"Expected '{expected_2}', but got '{result_2}'"

    # If we reach here, the assertions passed
    sys.exit(0)

if __name__ == "__main__":
    main()
