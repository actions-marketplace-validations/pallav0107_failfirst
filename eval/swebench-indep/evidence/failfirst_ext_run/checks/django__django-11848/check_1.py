import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key',
    )
django.setup()

from django.utils.http import parse_http_date
import time

def check_two_digit_year_logic():
    """
    Check if parse_http_date correctly handles two-digit years according to RFC 7231.
    
    RFC 7231 states:
    "Recipients of a timestamp value in rfc850-date format, which uses a
    two-digit year, MUST interpret a timestamp that appears to be more than
    50 years in the future as representing the most recent year in the past
    that had the same last two digits."
    
    This means the cutoff should be dynamic based on the current year, not
    hardcoded to 1970-2069.
    """
    
    # Get current year
    current_year = time.localtime().tm_year
    current_century = current_year // 100 * 100
    
    # Test case: A date with a two-digit year that would be > 50 years in the future
    # if interpreted in the current century, but should be interpreted as the previous century.
    
    # Example: If current year is 2023, then '99' should be 1999, not 2099.
    # '23' should be 2023 (or 2123? No, 2023 is now, so it's not > 50 years in future).
    # Let's pick a year that is definitely > 50 years in the future if placed in current century.
    
    # If current year is 2023:
    # 2023 + 50 = 2073. So any year >= 2074 is > 50 years in future.
    # Two digit year '74' -> if interpreted as 2074, that's > 50 years in future.
    # So it should be interpreted as 1974.
    
    # Let's construct an RFC 850 date with two-digit year '74'
    # Format: Weekday, DD-Mon-YY HH:MM:SS GMT
    # Example: Sunday, 01-Jan-74 00:00:00 GMT
    
    test_date_str = "Sunday, 01-Jan-74 00:00:00 GMT"
    
    try:
        parsed_time = parse_http_date(test_date_str)
    except Exception as e:
        print(f"Failed to parse date: {e}")
        sys.exit(1)
    
    # Convert parsed timestamp back to year
    parsed_year = time.gmtime(parsed_time).tm_year
    
    # Determine expected year
    # The two-digit year is 74.
    # Potential years: 1974 or 2074.
    # Current year: current_year
    # If 2074 is more than 50 years in the future from current_year, then it should be 1974.
    # i.e., if 2074 - current_year > 50, then expected is 1974.
    # Otherwise, if 2074 - current_year <= 50, then expected is 2074.
    
    potential_future_year = current_century + 74
    potential_past_year = current_century - 100 + 74
    
    if potential_future_year - current_year > 50:
        expected_year = potential_past_year
    else:
        expected_year = potential_future_year
    
    # Assert that the parsed year matches the expected year
    assert parsed_year == expected_year, f"Expected year {expected_year}, but got {parsed_year}. Current year is {current_year}."
    
    # Additional test: Ensure that a year within 50 years is kept in the current century
    # Pick a two-digit year that is within 50 years in the future
    # For example, if current year is 2023, then '25' -> 2025 is only 2 years in future.
    # So it should be 2025.
    
    test_date_str_2 = "Monday, 01-Jan-25 00:00:00 GMT"
    try:
        parsed_time_2 = parse_http_date(test_date_str_2)
    except Exception as e:
        print(f"Failed to parse date: {e}")
        sys.exit(1)
    
    parsed_year_2 = time.gmtime(parsed_time_2).tm_year
    
    potential_future_year_2 = current_century + 25
    potential_past_year_2 = current_century - 100 + 25
    
    if potential_future_year_2 - current_year > 50:
        expected_year_2 = potential_past_year_2
    else:
        expected_year_2 = potential_future_year_2
        
    assert parsed_year_2 == expected_year_2, f"Expected year {expected_year_2}, but got {parsed_year_2}. Current year is {current_year}."

if __name__ == '__main__':
    check_two_digit_year_logic()
    print("All checks passed.")
    sys.exit(0)
