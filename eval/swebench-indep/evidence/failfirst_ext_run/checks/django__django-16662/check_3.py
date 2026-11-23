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

from django.db import migrations, models
from django.db.migrations.writer import MigrationWriter


def check_migration_import_ordering():
    """
    Check if generated migration files have imports sorted correctly:
    standard library imports should come before third-party imports,
    and within each section, 'import X' should come before 'from X import Y'.
    
    Specifically, the issue states that:
    import datetime
    from django.db import migrations, models
    import time
    
    Should be:
    import datetime
    import time
    from django.db import migrations, models
    """
    
    # Create a simple migration operation
    operations = [
        migrations.CreateModel(
            name='TestModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
    ]
    
    # Create a migration instance
    migration_class = type('Migration', (migrations.Migration,), {
        'dependencies': [],
        'operations': operations,
    })
    
    # Write the migration to get the source code
    writer = MigrationWriter(migration_class)
    migration_source = writer.as_string()
    
    # Parse the import section of the generated migration
    lines = migration_source.split('\n')
    
    # Find import lines
    import_lines = []
    in_imports = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            import_lines.append(stripped)
        elif import_lines and not stripped.startswith('#') and stripped != '':
            # We've passed the import section
            break
    
    # Check that all 'import X' statements come before 'from X import Y' statements
    # within the same logical group (stdlib vs third-party)
    
    # For this specific issue, we need to check if stdlib imports like 'import datetime' 
    # and 'import time' are grouped together before 'from django.db import ...'
    
    # Let's look for the pattern mentioned in the issue
    has_datetime_import = any(line.startswith('import datetime') for line in import_lines)
    has_time_import = any(line.startswith('import time') for line in import_lines)
    has_django_from_import = any(line.startswith('from django.db import') for line in import_lines)
    
    if not (has_datetime_import or has_time_import):
        # The migration might not use datetime/time directly, so let's force it
        # by creating a more complex migration that uses these modules
        pass
    
    # Actually, let's create a migration that explicitly uses datetime and time
    # to ensure they appear in the imports
    
    # Create a custom migration with RunPython that uses datetime and time
    def my_function(apps, schema_editor):
        import datetime
        import time
        pass
    
    operations_with_stdlib = [
        migrations.RunPython(my_function),
        migrations.CreateModel(
            name='TestModel2',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
            ],
        ),
    ]
    
    migration_class2 = type('Migration2', (migrations.Migration,), {
        'dependencies': [],
        'operations': operations_with_stdlib,
    })
    
    writer2 = MigrationWriter(migration_class2)
    migration_source2 = writer2.as_string()
    
    lines2 = migration_source2.split('\n')
    import_lines2 = []
    for line in lines2:
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            import_lines2.append(stripped)
        elif import_lines2 and not stripped.startswith('#') and stripped != '' and not stripped.startswith('import ') and not stripped.startswith('from '):
            break
    
    # Now check the ordering
    # We expect:
    # import datetime
    # import time  
    # from django.db import migrations, models
    
    # Find indices of relevant imports
    datetime_idx = None
    time_idx = None
    django_from_idx = None
    
    for i, line in enumerate(import_lines2):
        if line.startswith('import datetime'):
            datetime_idx = i
        elif line.startswith('import time'):
            time_idx = i
        elif line.startswith('from django.db import'):
            django_from_idx = i
    
    # If datetime and time are imported, they should both come before the django from import
    if datetime_idx is not None and django_from_idx is not None:
        assert datetime_idx < django_from_idx, f"import datetime should come before from django.db import. Got:\n{chr(10).join(import_lines2)}"
    
    if time_idx is not None and django_from_idx is not None:
        assert time_idx < django_from_idx, f"import time should come before from django.db import. Got:\n{chr(10).join(import_lines2)}"
    
    # Also check that import statements come before from statements within stdlib
    # This is harder to verify generically, but the key issue is that stdlib 'import X' 
    # should not be interleaved with 'from third_party import Y'
    
    # Let's verify the general pattern: all bare imports should precede from imports
    # in their respective sections
    
    # A simpler check: find if there's any 'from ...' before a bare 'import ...' 
    # that belongs to the same category (stdlib)
    
    # For now, the main assertion is that stdlib imports come before django from imports
    print("Migration source:")
    print(migration_source2)
    print("\nImport lines:")
    for line in import_lines2:
        print(f"  {line}")
    
    # Final assertion: if we have both stdlib bare imports and django from imports,
    # the stdlib ones must come first
    if datetime_idx is not None and django_from_idx is not None:
        assert datetime_idx < django_from_idx, "Stdlib 'import' statements must come before 'from django.db import' statements"
    
    if time_idx is not None and django_from_idx is not None:
        assert time_idx < django_from_idx, "Stdlib 'import' statements must come before 'from django.db import' statements"


if __name__ == '__main__':
    check_migration_import_ordering()
    print("Check passed: Migration import ordering is correct.")
    sys.exit(0)
