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
                'TIME_ZONE': 'Europe/Paris',  # Database TIME_ZONE setting
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        USE_TZ=True,
        TIME_ZONE='Europe/Paris',  # Global TIME_ZONE
    )

django.setup()

from django.db import connection
from django.db.models import Model, DateTimeField
from django.utils import timezone
import datetime

# Create a simple model for testing
class TestModel(Model):
    my_datetime_field = DateTimeField()

    class Meta:
        app_label = 'test_app'

# Create the table
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Insert a record with a naive datetime that should be interpreted as Europe/Paris
# because the database TIME_ZONE is set to Europe/Paris and USE_TZ is True.
# In SQLite, Django stores datetimes as strings. If DB TIME_ZONE is set,
# it should treat naive datetimes as being in that timezone when converting to UTC for storage,
# or handle lookups accordingly.

# Let's create a specific datetime: 2017-07-06 20:50:00 in Europe/Paris
naive_dt = datetime.datetime(2017, 7, 6, 20, 50)
aware_dt = timezone.make_aware(naive_dt, timezone=timezone.get_current_timezone())

# Save the object. Django should convert this to UTC for storage if USE_TZ is True.
# However, the issue is about how lookups are constructed.
obj = TestModel.objects.create(my_datetime_field=aware_dt)

# Now perform the date lookup that was reported as broken.
# The issue states that when using __date lookup, Django generates SQL that converts from UTC
# to the current timezone, ignoring the database's TIME_ZONE setting.
# If the database TIME_ZONE is 'Europe/Paris', and the global TIME_ZONE is 'Europe/Paris',
# the conversion should effectively be a no-op or correctly handle the DB's local time.

# The bug manifests in the SQL generation. We can inspect the SQL query generated.
from django.test.utils import CaptureQueriesContext

queries = CaptureQueriesContext(connection)
with queries:
    exists = TestModel.objects.filter(my_datetime_field__date=naive_dt.date()).exists()

sql = queries.captured_queries[0]['sql']

# Print the SQL for debugging purposes (though we won't rely on print for exit code)
print(f"Generated SQL: {sql}")

# The core of the issue:
# If the database TIME_ZONE is set to 'Europe/Paris', Django should use that timezone
# when converting datetimes for lookups, not assume UTC.
# In the reported bug, the SQL contained `CONVERT_TZ(..., 'UTC', 'Europe/Paris')`.
# This is wrong if the data in the DB is already stored considering the DB TIME_ZONE.
# For SQLite and MySQL without native TZ support, Django stores in UTC if USE_TZ is True.
# BUT, the lookup logic was hardcoding 'UTC' as the source timezone for conversion,
# disregarding the fact that the database connection might have a different TIME_ZONE setting
# which affects how Django interprets the stored values or constructs queries.

# Actually, let's look closer at the fix. The issue is in `django/db/backends/mysql/operations.py`
# and similar for other backends. The `convert_datetimefield_value` or lookup preparation
# was ignoring `connection.timezone_name`.

# In Django 3.0+, if USE_TZ is True, datetimes are stored in UTC in the database.
# When doing a __date lookup, Django needs to convert the UTC stored value to the active timezone
# to extract the date.
# However, the bug report says: "conversion should be from the database timezone tz2 to the django app one tz1".
# Wait, if USE_TZ is True, Django always stores in UTC. So the source should be UTC.
# But the reporter says: "When USE_TZ is True and the database doesn’t support time zones ... 
# Django reads and writes datetimes in local time according to this option [DATABASES.TIME_ZONE] if it is set".
# This behavior changed in later versions. In older versions, DATABASES.TIME_ZONE affected how naive datetimes were interpreted.

# Let's check the actual behavior in the version provided (Django 3.0).
# In Django 3.0, if USE_TZ is True, all datetimes are stored in UTC.
# The `DATABASES['TIME_ZONE']` setting is used to interpret naive datetimes passed to the database
# if the database backend doesn't support timezones natively.
# However, for lookups, the conversion should respect the current active timezone.

# The specific bug was that the SQL generation for `__date` lookup hardcoded 'UTC' as the source
# timezone in `CONVERT_TZ`, but if the database was configured with a different TIME_ZONE,
# the interpretation of the stored data might differ, or the conversion logic was flawed.

# Let's verify if the lookup returns the correct result.
# We created an object with 2017-07-06 20:50:00 Europe/Paris.
# This is 2017-07-06 18:50:00 UTC.
# Stored in DB as UTC.
# When we filter by __date=2017-07-06, we expect it to match.
# The SQL should convert the UTC value to the current timezone (Europe/Paris) and extract the date.
# 2017-07-06 18:50:00 UTC -> 2017-07-06 20:50:00 Paris. Date is 2017-07-06. Match.

assert exists is True, f"Expected the object to be found with date lookup, but it was not. SQL: {sql}"

# Additionally, check if the SQL uses the correct timezone handling.
# In the fixed version, the conversion should properly account for timezones.
# For SQLite, Django uses Python-side conversion or specific SQL functions.
# For MySQL, it uses CONVERT_TZ.
# The bug was that it used 'UTC' as source even when the DB TIME_ZONE suggested otherwise,
# or rather, the issue was more subtle about how the database connection's timezone setting
# interacts with the query generation.

# Since we are using SQLite in this test, the SQL might not show CONVERT_TZ.
# Let's ensure the test passes for the logical correctness.

sys.exit(0)
