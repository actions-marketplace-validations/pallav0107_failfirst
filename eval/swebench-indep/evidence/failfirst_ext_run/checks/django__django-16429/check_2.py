import os
import sys
import django

# Configure Django settings minimally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        USE_TZ=True,
        TIME_ZONE='UTC',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )

django.setup()

import datetime
from django.utils import timezone
from django.utils.timesince import timesince

def main():
    # Reproduce the issue:
    # timesince() raises TypeError with USE_TZ=True and >1 month interval.
    
    # Get current time (aware because USE_TZ=True)
    now = timezone.now()
    
    # Create a datetime 31 days in the past
    # Since 'now' is aware, subtracting timedelta keeps it aware
    d = now - datetime.timedelta(days=31)
    
    # This should not raise TypeError: can't subtract offset-naive and offset-aware datetimes
    try:
        result = timesince(d)
    except TypeError as e:
        if "can't subtract offset-naive and offset-aware datetimes" in str(e):
            print(f"Issue reproduced: {e}")
            sys.exit(1)
        else:
            # Some other TypeError, re-raise or handle appropriately
            raise
    
    # Verify the result is roughly what we expect ("1 month")
    # The exact string might vary slightly depending on implementation details 
    # but it should contain "month"
    assert "month" in result, f"Expected 'month' in result, got: {result}"
    
    print(f"Success: timesince returned '{result}'")
    sys.exit(0)

if __name__ == '__main__':
    main()
