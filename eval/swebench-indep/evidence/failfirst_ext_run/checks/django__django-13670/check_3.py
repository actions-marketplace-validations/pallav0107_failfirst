import sys
import datetime

# Configure Django settings minimally before importing django.utils.dateformat
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
    # PHP's date("y") returns '23' for year 123.
    # The expected behavior is a two-digit year with leading zero if necessary.
    
    test_date = datetime.datetime(123, 4, 5, 6, 7)
    
    # Get the result from Django's dateformat with 'y' specifier
    result = dateformat.format(test_date, "y")
    
    # Expected result is '23' (last two digits of 123)
    expected = "23"
    
    # Assert that the result matches the expected behavior
    assert result == expected, f"Expected '{expected}', but got '{result}'"
    
    # Additional check for another edge case: year 9
    test_date_2 = datetime.datetime(9, 1, 1)
    result_2 = dateformat.format(test_date_2, "y")
    expected_2 = "09"
    assert result_2 == expected_2, f"Expected '{expected_2}', but got '{result_2}'"

    # Additional check for year 99
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

if __name__ == "__main__":
    main()
