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
            },
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        USE_TZ=True,
        TIME_ZONE='Europe/Paris',  # Global app timezone
    )

django.setup()

from django.db import connection
from django.db.models import Model, DateTimeField
from django.utils import timezone
import datetime

# Check if the backend operations class has the fix.
# The issue states that MySQL, SQLite, and Oracle ignore the DATABASES['TIME_ZONE']
# when doing date lookups, specifically forcing 'UTC' as the source timezone in CONVERT_TZ
# or equivalent logic.

# For SQLite, the relevant code is in django/db/backends/sqlite3/operations.py
# For MySQL, it's in django/db/backends/mysql/operations.py
# For Oracle, it's in django/db/backends/oracle/operations.py

# The bug is in the `date_extract_sql` or similar methods used for __date lookups.
# In older versions, it might have hardcoded 'UTC'. In fixed versions, it should use
# self.connection.timezone_name or respect the database TIME_ZONE setting.

# Let's inspect the source code of the operations module for the current backend.
backend = connection.vendor
ops = connection.ops

# We need to verify if the SQL generated for a __date lookup respects the db TIME_ZONE.
# Since we can't easily run a full query with data insertion and verification in a 
# read-only check without creating tables (which might be considered modifying state, 
# though in-memory is fine), let's look at the SQL generation logic directly.

# Create a dummy model to trigger compiler SQL generation
class DummyModel(Model):
    created_at = DateTimeField()
    
    class Meta:
        app_label = 'test'

# Compile a query with __date lookup
from django.db.models.sql.query import Query
from django.db.models.sql.compiler import SQLCompiler

query = Query(DummyModel)
query.add_filter(('created_at__date', datetime.date(2017, 7, 6)))

compiler = query.get_compiler(using='default')
try:
    sql, params = compiler.as_sql()
except Exception as e:
    # If compilation fails, we might need to setup DB tables, but let's try to inspect ops first.
    # Fallback: Inspect the source code of the operation method responsible for date extraction.
    pass

# The core of the issue is in how the backend handles timezone conversion for date lookups.
# In Django 3.0, for SQLite, the `datetime_extract_sql` or `date_extract_sql` might be involved.
# Actually, for `__date`, Django uses `DATE()` function in SQLite.
# The issue description mentions `CONVERT_TZ` for MySQL. For SQLite, it's different.
# However, the issue title says "TIME_ZONE value in DATABASES settings is not used... on MySQL, SQLite, and Oracle".

# Let's check the `connection.timezone_name` property.
# If the database TIME_ZONE is set, `connection.timezone_name` should reflect it.
db_tz_setting = settings.DATABASES['default'].get('TIME_ZONE')
actual_tz_name = connection.timezone_name

# In Django, if USE_TZ is True and the backend doesn't support timezones natively (like SQLite),
# it simulates them. The `connection.timezone_name` should be the one from settings if provided,
# otherwise UTC.

assert actual_tz_name == db_tz_setting, f"Expected connection.timezone_name to be '{db_tz_setting}', but got '{actual_tz_name}'. The DATABASES TIME_ZONE setting is being ignored."

# Now, let's verify the SQL generation for a date lookup includes the correct timezone handling.
# For SQLite, Django converts datetimes to the local timezone before extracting the date.
# The SQL should involve converting from UTC (storage) to the DB timezone (Europe/Paris).
# Wait, if the DB timezone is Europe/Paris, Django stores in UTC? 
# No, if USE_TZ is True, Django always stores in UTC in the DB for backends that don't support TZ.
# But when querying, it converts from UTC to the current timezone (or DB timezone?) for filtering.

# The issue says: "conversion should be from the database timezone tz2 to the django app one tz1".
# Actually, Django stores in UTC. So conversion should be FROM UTC TO the timezone used for comparison.
# The bug was that it was hardcoding UTC as the *target* or *source* incorrectly, or ignoring the DB TZ setting
# which defines what "local time" means for that connection.

# Let's look at the specific method in ops.
import inspect

# Get the source of the method responsible for date extraction or lookup preparation.
# In Django 3.0, for SQLite, `ops.datetime_cast_date_sql` or similar might be used.
# Or `ops.prepare_value`.

# A more robust check: Verify that `connection.timezone_name` is correctly set.
# This is the primary indicator that the setting is picked up.
# If this is correct, the SQL generation usually follows suit.

# Let's also check if the SQL contains the expected timezone string if applicable.
# For SQLite, the SQL might not explicitly show the timezone name in the same way MySQL does with CONVERT_TZ,
# but the logic in Python side or SQL functions should respect it.

# Since we asserted `connection.timezone_name` is correct, let's ensure the SQL compiler uses it.
# We'll create a simple test case with actual SQL generation.

from django.db import models

class TestModel(models.Model):
    dt = models.DateTimeField()
    class Meta:
        app_label = 'myapp'

# Force creation of table in memory
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(TestModel)

# Insert a record
obj = TestModel.objects.create(dt=datetime.datetime(2017, 7, 6, 20, 50, tzinfo=timezone.get_current_timezone()))

# Perform the date lookup
# The issue is that __date lookup failed to find the object because of wrong TZ conversion.
qs = TestModel.objects.filter(dt__date=datetime.date(2017, 7, 6))
sql = str(qs.query)

# Check if the query returns the object
exists = qs.exists()

# If the bug is present, the conversion might be wrong, leading to False.
# With the fix, it should be True.
assert exists is True, f"The __date lookup failed to find the object. Generated SQL: {sql}. This indicates the TIME_ZONE setting is not being used correctly for date lookups."

sys.exit(0)
