import os
import sys
import datetime

# Configure Django settings minimally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-script-only',
    )

django.setup()

from django.utils.http import parse_http_date

def check_two_digit_year_logic():
    """
    RFC 7231 states:
    "Recipients of a timestamp value in rfc850-date format, which uses a
    two-digit year, MUST interpret a timestamp that appears to be more than
    50 years in the future as representing the most recent year in the past
    that had the same last two digits."
    
    This means the cutoff is dynamic based on the current year, not hardcoded
    to 1970-2069.
    
    Example: If current year is 2023:
    - Two digit year '23' -> 2023 (current)
    - Two digit year '24' -> 2024 (next year, < 50 years in future)
    - Two digit year '73' -> 1973? No. 2073 is > 50 years in future from 2023.
      So 2073 is interpreted as 1973. Wait, 2023 + 50 = 2073. 
      "More than 50 years in the future". 
      So if the parsed year is > current_year + 50, it should be shifted back 100 years.
      
    Let's pick a specific test case that distinguishes between the old hardcoded logic
    and the correct dynamic logic.
    
    Old logic: 0-69 -> 2000-2069, 70-99 -> 1970-1999.
    
    Suppose current year is 2023.
    Consider two-digit year '22'. 
    Old logic: 2022.
    New logic: 2022 is within 50 years of 2023 (it's in the past), so 2022. Same.
    
    Consider two-digit year '80'.
    Old logic: 1980.
    New logic: Current year 2023. 2080 is 57 years in the future (> 50). So interpret as 1980. Same.
    
    We need a case where they differ.
    The old logic switches at 69/70.
    The new logic switches at (current_year % 100) + 50 roughly.
    
    Let's assume the current year is 2023 (or whatever the system time is).
    Let Y = current year.
    Let y = two digit year.
    Candidate full year = 2000 + y if y <= 69 else 1900 + y (OLD LOGIC).
    
    NEW LOGIC:
    Base century = current century (e.g., 2000).
    Full year = base_century + y.
    If Full year > current_year + 50:
        Full year -= 100
        
    Let's find a y where OLD != NEW.
    
    If current year is 2023:
    Cutoff for new logic: 2023 + 50 = 2073.
    Years 2000..2073 are kept as 20xx.
    Years 2074..2099 are shifted to 19xx.
    So y=74 -> 2074 -> shift to 1974.
    Old logic for y=74: 1974.
    They match here too.
    
    Wait, let's look closer at the old logic: 0-69 -> 2000s, 70-99 -> 1900s.
    New logic for 2023:
    y=0..73 -> 2000..2073 (kept as 20xx because 2073 <= 2073).
    y=74..99 -> 2074..2099 (shifted to 19xx because > 2073).
    
    So for y=70, 71, 72, 73:
    Old logic: 1970, 1971, 1972, 1973.
    New logic: 2070, 2071, 2072, 2073.
    
    These are different!
    
    So if we use a date with two-digit year 70, 71, 72, or 73, and the current year is >= 2023,
    the old logic returns 197x, but the correct logic returns 207x.
    
    Let's verify the "more than 50 years in the future" rule.
    Current year: 2023.
    Candidate: 2070.
    Difference: 2070 - 2023 = 47 years.
    47 is NOT more than 50. So 2070 is valid as 2070.
    
    Candidate: 2073.
    Difference: 50 years. Not MORE than 50. So 2073 is valid as 2073.
    
    Candidate: 2074.
    Difference: 51 years. More than 50. So shift to 1974.
    
    So for current year 2023:
    y=70 -> New: 2070, Old: 1970. DIFFERENT.
    
    Therefore, we can test this by constructing an RFC 850 date with a two-digit year
    like 70, 71, 72, or 73, and checking if the parsed year is in the 2000s (correct)
    or 1900s (incorrect/old behavior).
    """
    
    now = datetime.datetime.now(datetime.timezone.utc)
    current_year = now.year
    
    # We need a two-digit year Y such that:
    # 1. Under old logic (0-69->2000s, 70-99->1900s), it maps to 1900s. So Y >= 70.
    # 2. Under new logic, it maps to 2000s. This happens if (2000 + Y) <= (current_year + 50).
    #    i.e., Y <= current_year % 100 + 50.
    
    # Let's pick Y = 70.
    # Old logic: 1970.
    # New logic target year: 2070.
    # Condition for new logic to keep 2070: 2070 <= current_year + 50
    # => current_year >= 2020.
    
    # Since Django 3.1 was released in 2020, and we are likely running in 2020+,
    # this test should work. If current_year < 2020, we might need a different Y.
    # But given the context, current_year is almost certainly >= 2020.
    
    # To be safe, let's calculate a suitable Y dynamically.
    # We want Y where Old(Y) != New(Y).
    # Old(Y) = 1900 + Y if Y >= 70 else 2000 + Y
    # New(Y) = 2000 + Y if (2000+Y) <= (current_year + 50) else 1900 + Y
    
    # Case 1: Y >= 70.
    # Old(Y) = 1900 + Y.
    # New(Y) = 2000 + Y if Y <= current_year - 2000 + 50 else 1900 + Y.
    # Let limit = current_year - 2000 + 50 = current_year - 1950.
    # If 70 <= Y <= limit, then Old=19xx, New=20xx. Different!
    
    # So we need limit >= 70.
    # current_year - 1950 >= 70 => current_year >= 2020.
    
    if current_year < 2020:
        # Fallback for very old systems, though unlikely for Django 3.1 context
        # If current_year is 2019, limit = 69. No Y >= 70 satisfies Y <= 69.
        # We'd need Y < 70.
        # Case 2: Y < 70.
        # Old(Y) = 2000 + Y.
        # New(Y) = 2000 + Y if (2000+Y) <= (current_year + 50) else 1900 + Y.
        # If 2000 + Y > current_year + 50, New(Y) = 1900 + Y.
        # Then Old=20xx, New=19xx. Different!
        # Condition: Y > current_year + 50 - 2000 = current_year - 1950.
        # And Y < 70.
        # For current_year = 2019, limit = 69. Y > 69 and Y < 70. No integer.
        # For current_year = 2018, limit = 68. Y > 68 and Y < 70 => Y=69.
        # Old(69) = 2069. New(69): 2069 > 2018+50=2068? Yes. So New=1969.
        # So for current_year <= 2019, we can use Y=69 if current_year <= 2018.
        
        # This is getting complex. Let's just assume current_year >= 2020 for Django 3.1.
        # If not, we'll try to handle it.
        pass

    # Let's just use Y=70 and assert that the result is 2070 if current_year >= 2020.
    # If current_year < 2020, the "correct" behavior according to RFC would still be dynamic,
    # but the difference might manifest differently. However, Django 3.1 requires Python 3.6+
    # and was active in 2020/2021. It's safe to assume current_year >= 2020.
    
    # Construct an RFC 850 date string with two-digit year 70.
    # Format: Weekday, DD-Mon-YY HH:MM:SS GMT
    # Example: Sunday, 01-Jan-70 00:00:00 GMT
    
    test_date_str = "Sunday, 01-Jan-70 00:00:00 GMT"
    
    parsed_dt = parse_http_date(test_date_str)
    
    # parsed_dt is a datetime object (naive, treated as UTC usually by caller, but parse_http_date returns naive)
    # Check the year
    parsed_year = parsed_dt.year
    
    # Expected behavior according to RFC 7231 with current_year >= 2020:
    # 2070 is within 50 years of current year (e.g., 2023 + 50 = 2073 >= 2070).
    # So it should be interpreted as 2070.
    
    # If the bug is present (hardcoded 70-99 -> 1900s), it will be 1970.
    
    if current_year >= 2020:
        expected_year = 2070
    else:
        # For completeness, though unlikely to be run in such environment for this Django version
        # Calculate dynamically
        candidate = 2070
        if candidate > current_year + 50:
            expected_year = 1970
        else:
            expected_year = 2070
            
    assert parsed_year == expected_year, (
        f"Incorrect two-digit year parsing. "
        f"Current year is {current_year}. "
        f"Parsed year for '70' is {parsed_year}, expected {expected_year}. "
        f"This indicates the hardcoded 1970-1999/2000-2069 logic is still in place."
    )

if __name__ == '__main__':
    check_two_digit_year_logic()
    print("Check passed: Two-digit year logic is correct (dynamic based on current year).")
    sys.exit(0)
