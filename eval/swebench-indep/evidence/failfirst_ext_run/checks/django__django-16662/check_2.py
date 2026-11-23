import os
import sys
import tempfile
import shutil

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

from django.core.management import call_command
from django.db import connection
from django.db.migrations.writer import MigrationWriter
from django.db.migrations import Migration, operations
from django.db.models import Model, CharField


def test_migration_import_ordering():
    """
    Test that generated migration files have imports sorted such that
    'import module' statements come before 'from module import ...' statements.
    
    According to the issue, the correct order should be:
    import datetime
    import time
    from django.db import migrations, models
    
    Not:
    import datetime
    from django.db import migrations, models
    import time
    """
    
    # Create a simple migration with operations that require various imports
    # We need to trigger imports like datetime, time, etc. to see the ordering
    
    class TestModel(Model):
        name = CharField(max_length=100)
        
        class Meta:
            app_label = 'test_app'
    
    # Create a migration with operations that will generate various imports
    migration = Migration("0001_initial", "test_app")
    migration.operations = [
        operations.CreateModel(
            name='TestModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
    
    # Write the migration to get the string representation
    writer = MigrationWriter(migration)
    migration_string = writer.as_string()
    
    # Parse the imports from the generated migration string
    lines = migration_string.split('\n')
    
    # Find the import section (lines starting with 'import' or 'from')
    import_lines = []
    in_import_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            import_lines.append(stripped)
            in_import_section = True
        elif in_import_section and stripped and not stripped.startswith('#'):
            # End of import section when we hit non-import, non-comment, non-empty line
            break
    
    # Check that all 'import X' lines come before any 'from X import Y' lines
    found_from_import = False
    for line in import_lines:
        if line.startswith('from '):
            found_from_import = True
        elif line.startswith('import '):
            # If we've already seen a 'from' import, then an 'import' after it is wrong
            assert not found_from_import, (
                f"Import ordering violation: 'import' statement appears after 'from' import.\n"
                f"Generated imports:\n" + "\n".join(import_lines) + "\n"
                f"Full migration:\n{migration_string}"
            )
    
    # Additional check: verify specific pattern mentioned in issue
    # The issue mentions that datetime and time imports should come before django.db imports
    import_indices = {}
    for i, line in enumerate(import_lines):
        if line.startswith('import datetime'):
            import_indices['datetime'] = i
        elif line.startswith('import time'):
            import_indices['time'] = i
        elif line.startswith('from django.db'):
            import_indices['django_db'] = i
    
    # If both datetime/time and django.db imports exist, check ordering
    if 'datetime' in import_indices and 'django_db' in import_indices:
        assert import_indices['datetime'] < import_indices['django_db'], (
            f"'import datetime' should come before 'from django.db ...'\n"
            f"Generated imports:\n" + "\n".join(import_lines)
        )
    
    if 'time' in import_indices and 'django_db' in import_indices:
        assert import_indices['time'] < import_indices['django_db'], (
            f"'import time' should come before 'from django.db ...'\n"
            f"Generated imports:\n" + "\n".join(import_lines)
        )


if __name__ == '__main__':
    try:
        test_migration_import_ordering()
        print("PASS: Migration import ordering is correct.")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(2)
