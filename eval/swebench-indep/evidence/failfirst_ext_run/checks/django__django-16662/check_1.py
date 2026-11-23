import os
import sys
import tempfile
import shutil

# Configure Django settings
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
            'test_app',
        ],
        SECRET_KEY='fake-secret-key-for-testing-only',
    )

django.setup()

# Create a temporary app to test migration generation
temp_dir = tempfile.mkdtemp()
sys.path.insert(0, temp_dir)

app_dir = os.path.join(temp_dir, 'test_app')
os.makedirs(app_dir)

# Create __init__.py
with open(os.path.join(app_dir, '__init__.py'), 'w') as f:
    f.write('')

# Create models.py with a simple model to trigger migration creation
with open(os.path.join(app_dir, 'models.py'), 'w') as f:
    f.write('''
from django.db import models

class TestModel(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'test_app'
''')

try:
    from django.core.management import call_command
    from io import StringIO
    
    # Generate migrations
    out = StringIO()
    call_command('makemigrations', 'test_app', stdout=out, verbosity=0)
    
    # Find the generated migration file
    migrations_dir = os.path.join(app_dir, 'migrations')
    migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py') and f != '__init__.py']
    
    assert len(migration_files) > 0, "No migration files were generated"
    
    # Read the first migration file
    migration_path = os.path.join(migrations_dir, migration_files[0])
    with open(migration_path, 'r') as f:
        content = f.read()
    
    # Parse the imports section
    lines = content.split('\n')
    
    # Find import lines
    import_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            import_lines.append(stripped)
    
    # Check that all 'import module' statements come before 'from module import' statements
    last_import_module_index = -1
    first_from_import_index = len(import_lines)
    
    for i, line in enumerate(import_lines):
        if line.startswith('import ') and not line.startswith('import '):
            # This is just 'import X'
            pass
        
        if line.startswith('import '):
            last_import_module_index = max(last_import_module_index, i)
        elif line.startswith('from '):
            if first_from_import_index == len(import_lines):
                first_from_import_index = i
    
    # The issue states that 'import module' should come before 'from module import'
    # So if we have both types, last_import_module_index should be < first_from_import_index
    if last_import_module_index != -1 and first_from_import_index != len(import_lines):
        assert last_import_module_index < first_from_import_index, \
            f"Import ordering is incorrect: 'import' statements should come before 'from' statements. " \
            f"Found import at index {last_import_module_index} and from at index {first_from_import_index}. " \
            f"Imports: {import_lines}"
    
    print("Migration import ordering is correct.")
    sys.exit(0)

except AssertionError as e:
    print(f"Assertion failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
    if temp_dir in sys.path:
        sys.path.remove(temp_dir)
