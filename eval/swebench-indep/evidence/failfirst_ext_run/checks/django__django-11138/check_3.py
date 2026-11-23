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
                'TIME_ZONE': 'Europe/Paris',  # Database timezone setting
            }
        },
        USE_TZ=True,
        TIME_ZONE='UTC',  # Global app timezone
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )

django.setup()

from django.db import connection, models
from django.utils import timezone
import datetime

# Define a simple model for testing
class TestModel(models.Model):
    my_datetime_field = models.DateTimeField()

    class Meta:
        app_label = 'test_app'

# Create the table
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Insert a record with a naive datetime that represents local time in Europe/Paris
# The database TIME_ZONE is 'Europe/Paris'.
# When USE_TZ=True and DB has TIME_ZONE, Django should treat naive datetimes as being in that TZ when saving?
# Actually, let's look at how Django handles this.
# If we save a naive datetime, Django typically assumes it's in UTC if USE_TZ is True, 
# BUT if the backend supports TIME_ZONE setting, it might convert.
# However, the issue is about LOOKUPs.

# Let's manually insert a value to be sure of what's in the DB.
# In SQLite with TIME_ZONE set, Django's operations.py uses CONVERT_TZ equivalent logic?
# Actually, SQLite doesn't have native TZ support like MySQL. Django emulates it.
# The issue states: "Django reads and writes datetimes in local time according to this option if it is set"
# So if DB TIME_ZONE is 'Europe/Paris', a naive datetime '2017-07-06 20:50:00' saved to DB 
# should be stored as is (local time), but interpreted as Paris time.

# Let's create a record.
# We need to bypass Django's conversion to ensure the raw value in the DB matches the scenario.
# Or we can use Django's ORM correctly.

# Scenario:
# DB TIME_ZONE: Europe/Paris
# App TIME_ZONE: UTC
# USE_TZ: True

# We want to filter by date.
# dt = timezone.make_aware(datetime.datetime(2017, 7, 6, 20, 50), timezone.get_current_timezone())
# Current timezone is UTC (global). So dt is 2017-07-06 20:50 UTC.
# In Paris time, this is 2017-07-06 22:50 CEST.
# If the DB stores values in Paris time (because DB TIME_ZONE is Paris), 
# then a value stored as '2017-07-06 22:50:00' in the DB corresponds to 20:50 UTC.

# Let's insert a row directly into the database to simulate a legacy DB or just to control the value.
# The value in the DB column will be '2017-07-06 22:50:00' (naive, but conceptually Paris time).

from django.db import connection

cursor = connection.cursor()
# Insert a naive datetime string. Since DB TIME_ZONE is Europe/Paris, this is interpreted as Paris time.
cursor.execute("INSERT INTO test_app_testmodel (my_datetime_field) VALUES ('2017-07-06 22:50:00')")

# Now perform the lookup.
# We want to find objects where the date in the DB's local time (Paris) is 2017-07-06.
# The object we inserted has Paris time 22:50 on 2017-07-06.
# So filtering by date=2017-07-06 should return this object.

# How do we express this filter?
# MyModel.objects.filter(my_datetime_field__date=datetime.date(2017, 7, 6))
# This lookup converts the field to the current timezone (UTC) before extracting the date?
# Or does it respect the DB timezone?

# The issue says: "When USE_TZ is True, fields are converted to the current time zone before filtering"
# Current timezone is UTC.
# The value in DB is '2017-07-06 22:50:00' (Paris).
# Converted to UTC, it becomes '2017-07-06 20:50:00'.
# The date in UTC is 2017-07-06.
# So the filter __date=datetime.date(2017, 7, 6) SHOULD match.

# However, the bug report says that the SQL generated uses CONVERT_TZ(field, 'UTC', 'Europe/Paris').
# This implies it thinks the field is in UTC and converts to Paris.
# But the field is already in Paris time (because DB TIME_ZONE is Paris).
# So it should convert from Paris to UTC (or no conversion if comparing in Paris time?).

# Let's check the result.
obj = TestModel.objects.filter(my_datetime_field__date=datetime.date(2017, 7, 6)).first()

# If the bug is present, the conversion might be wrong, leading to no match or wrong match.
# Specifically, if it converts FROM UTC TO Paris, it treats '2017-07-06 22:50:00' as UTC.
# 22:50 UTC -> 00:50 Paris (next day). Date becomes 2017-07-07. No match.
# If it works correctly, it should recognize the DB time is Paris, convert to UTC (20:50), date is 2017-07-06. Match.

assert obj is not None, "The object should be found when filtering by date considering the database TIME_ZONE setting."

# Clean up
cursor.execute("DELETE FROM test_app_testmodel")
cursor.close()

sys.exit(0)
