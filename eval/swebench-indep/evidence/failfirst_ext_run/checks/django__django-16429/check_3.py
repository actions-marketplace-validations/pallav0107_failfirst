import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={},
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        USE_TZ=True,
        TIME_ZONE='UTC',
    )

django.setup()

import datetime
from django.utils import timezone
from django.utils.timesince import timesince

def test_long_interval_with_tz():
    """
    Reproduce the issue: timesince() raises TypeError with USE_TZ=True and >1 month interval.
    """
    # Ensure USE_TZ is True as per the issue description
    assert settings.USE_TZ is True
    
    now = timezone.now()
    # Create a datetime 31 days in the past. 
    # timezone.now() returns an aware datetime if USE_TZ is True.
    # Subtracting a timedelta from an aware datetime results in an aware datetime.
    d = now - datetime.timedelta(days=31)
    
    # This call should not raise TypeError: can't subtract offset-naive and offset-aware datetimes
    try:
        result = timesince(d)
    except TypeError as e:
        if "can't subtract offset-naive and offset-aware datetimes" in str(e):
            raise AssertionError(f"Bug reproduced: {e}")
        else:
            raise
            
    # Verify the result is as expected
    assert result == "1\xa0month", f"Expected '1\\xa0month', got '{result}'"

if __name__ == '__main__':
    test_long_interval_with_tz()
    print("Test passed: Issue is fixed.")
    sys.exit(0)
