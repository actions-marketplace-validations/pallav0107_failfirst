import os
import sys
import datetime

# Configure Django settings minimally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

try:
    import django
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            SECRET_KEY='test-secret-key-for-check-only',
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
            ],
        )
    django.setup()
except Exception as e:
    # If django setup fails, we might still be able to import the utility directly
    # but usually django.utils.http requires django to be configured.
    pass

from django.utils.http import parse_http_date

def check_behavior():
    """
    The issue states that the two-digit year check is incorrect.
    
    RFC 7231 says:
    "Recipients of a timestamp value in rfc850-date format, which uses a
    two-digit year, MUST interpret a timestamp that appears to be more than
    50 years in the future as representing the most recent year in the past
    that had the same last two digits."
    
    Current (buggy) logic: hard-coded 0-69 -> 2000-2069, 70-99 -> 1970-1999.
    Expected (fixed) logic: Compare against current year. If the resulting date
    is more than 50 years in the future, subtract 100 years.
    
    We need to test with a date that would be > 50 years in the future using
    the simple 20xx interpretation but should be interpreted as 19xx instead.
    
    Let's assume the current year is Y.
    If we parse a date with year YY such that 20YY > Y + 50, it should be interpreted as 19YY.
    
    For example, if current year is 2023:
    - 2023 + 50 = 2073.
    - Any year 2074-2099 should be rolled back to 1974-1999.
    - So 'Sunday, 01-Jan-74 00:00:00 GMT' 
      - Buggy logic: 74 >= 70, so 1974. This actually matches the expected behavior for 74.
      - Wait, the buggy logic is 0-69 -> 2000s, 70-99 -> 1900s.
      - The RFC says: if it appears > 50 years in future, treat as past.
      
    Let's look at a case where the buggy logic fails.
    Suppose current year is 2020.
    Threshold for "50 years in future" is 2070.
    Year '69': 
      - Buggy logic: 0-69 -> 2069.
      - 2069 is < 2020 + 50 (2070)? No, 2069 is 49 years in future. It is NOT more than 50 years in future.
      - So RFC says keep it as 2069. Buggy logic says 2069. Match.
      
    Year '70':
      - Buggy logic: 70-99 -> 1970.
      - 1970 is in the past. 
      - RFC: Interpret 2070. Is 2070 > 2020 + 50 (2070)? "More than 50 years". 2070 is exactly 50 years. Usually "more than" means >. So 2070 is not > 50 years in future. Keep 2070?
      - Actually, let's look at the standard library or common implementations. Python's email.utils parses RFC 2822/7231 dates.
      
    Let's re-read the issue carefully.
    "Current logic is hard coded to consider 0-69 to be in 2000-2069, and 70-99 to be in 1970-1999, instead of comparing versus the current year."
    
    This implies the fix makes it dynamic based on the current year.
    
    Consider a date far in the future according to the buggy logic but within 50 years according to RFC?
    Or vice versa?
    
    If current year is 2023:
    Buggy: 69 -> 2069. 2069 - 2023 = 46 years. <= 50. OK.
    Buggy: 70 -> 1970. 
    RFC: Try 2070. 2070 - 2023 = 47 years. Not > 50. So keep 2070.
    Buggy gives 1970. RFC gives 2070. MISMATCH.
    
    So, if we are in 2023, parsing a date with year 70 should yield 2070 (because 2070 is only 47 years away, not more than 50).
    The buggy code yields 1970.
    
    Therefore, to verify the fix:
    1. Get current year.
    2. Construct an RFC 850 date string with a two-digit year `YY` such that:
       - `20YY` is NOT more than 50 years in the future (i.e., `20YY <= current_year + 50`).
       - But `YY` falls in the range 70-99 (so buggy code maps it to 19YY).
       
    Example: Current year 2023.
    Pick YY = 70.
    2070 <= 2023 + 50 (2073). True.
    So correct behavior: 2070.
    Buggy behavior: 1970.
    
    We need to ensure we pick a YY that is >= 70 and <= 99, and 20YY <= current_year + 50.
    This requires current_year + 50 >= 2070 => current_year >= 2020.
    Since Django 3.1 was released in 2020, and we are likely running this later, this should hold.
    However, if we run this in 2019, 2070 > 2019+50 (2069), so RFC would say 1970. Buggy says 1970. Match.
    
    To be safe, let's pick a year that definitely exposes the bug in recent years.
    If current year is 2024:
    Threshold: 2074.
    YY=74. 2074 <= 2074? Yes (not MORE than 50 years). So RFC says 2074.
    Buggy says 1974.
    
    What if current year is 2060?
    Threshold: 2110.
    YY=10. Buggy: 2010. RFC: 2010 is in past. OK.
    YY=90. Buggy: 1990. RFC: Try 2090. 2090 - 2060 = 30 years. Not > 50. So 2090.
    Buggy gives 1990. RFC gives 2090. Mismatch.
    
    So generally, for any current year Y, if we pick YY such that:
    1. YY >= 70 (so buggy maps to 19YY)
    2. 20YY <= Y + 50 (so RFC keeps 20YY)
    
    This works if Y + 50 >= 2070, i.e., Y >= 2020.
    
    What if Y < 2020? E.g., 2019.
    Then 2070 > 2019 + 50 (2069). So RFC says 1970. Buggy says 1970. Match.
    In that case, we need a different YY.
    We need YY such that:
    1. YY <= 69 (so buggy maps to 20YY)
    2. 20YY > Y + 50 (so RFC rolls back to 19YY)
    
    If Y=2019, Y+50=2069.
    We need 20YY > 2069. Impossible for YY <= 69.
    
    So the bug only manifests when the current year is large enough that some years in 70-99 are within 50 years, OR small enough that some years in 0-69 are more than 50 years in future (which is impossible for 0-69 unless Y is very small, e.g. Y=1900).
    
    Given Django 3.1 context, we are likely in 2020+.
    
    Let's write the check dynamically.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    current_year = now.year
    
    # Find a test case
    # Case 1: Look for YY in 70-99 where 20YY is within 50 years (<= current + 50)
    # Expected: 20YY. Buggy: 19YY.
    target_yy_1 = None
    for yy in range(70, 100):
        full_year_buggy = 1900 + yy
        full_year_rfc = 2000 + yy
        if full_year_rfc <= current_year + 50:
            target_yy_1 = yy
            break
            
    # Case 2: Look for YY in 0-69 where 20YY is more than 50 years in future (> current + 50)
    # Expected: 19YY. Buggy: 20YY.
    target_yy_2 = None
    for yy in range(0, 70):
        full_year_buggy = 2000 + yy
        full_year_rfc_candidate = 2000 + yy
        if full_year_rfc_candidate > current_year + 50:
            target_yy_2 = yy
            break

    if target_yy_1 is not None:
        # Use this case
        yy = target_yy_1
        expected_year = 2000 + yy
        # Format: Sunday, 01-Jan-YY 00:00:00 GMT
        # We need to find a day of week for Jan 1, 20YY
        d = datetime.date(expected_year, 1, 1)
        day_name = d.strftime('%A')
        date_str = f"{day_name}, 01-Jan-{yy:02d} 00:00:00 GMT"
        
        parsed = parse_http_date(date_str)
        parsed_dt = datetime.datetime.fromtimestamp(parsed, tz=datetime.timezone.utc)
        
        assert parsed_dt.year == expected_year, (
            f"Failed for year {yy}. Expected {expected_year}, got {parsed_dt.year}. "
            f"Date string: {date_str}"
        )
        
    elif target_yy_2 is not None:
        # Use this case
        yy = target_yy_2
        expected_year = 1900 + yy
        d = datetime.date(expected_year, 1, 1)
        day_name = d.strftime('%A')
        date_str = f"{day_name}, 01-Jan-{yy:02d} 00:00:00 GMT"
        
        parsed = parse_http_date(date_str)
        parsed_dt = datetime.datetime.fromtimestamp(parsed, tz=datetime.timezone.utc)
        
        assert parsed_dt.year == expected_year, (
            f"Failed for year {yy}. Expected {expected_year}, got {parsed_dt.year}. "
            f"Date string: {date_str}"
        )
    else:
        # This should rarely happen unless we are in a very specific edge window
        # or the implementation is already correct and handles all cases.
        # If no discrepancy can be found with simple logic, we might assume it's fixed
        # or our test generation is flawed.
        # However, given the bug description, one of these cases should exist for most years.
        # For example, if current year is 2023:
        # Case 1: yy=70. 2070 <= 2073. Yes.
        pass

if __name__ == '__main__':
    check_behavior()
    print("Check passed.")
    sys.exit(0)
