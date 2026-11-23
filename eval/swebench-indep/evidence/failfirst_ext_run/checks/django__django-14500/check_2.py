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
        MIGRATION_MODULES={},
    )

django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import ProjectState
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder


def test_squashed_migration_unapply_behavior():
    """
    Test that when unapplying a squashed migration, if the replaced migrations
    are still present, the squashed migration itself should NOT be marked as
    unapplied (i.e., it should remain applied or be handled correctly).
    
    The issue states: "When unapplying a squashed migration and the replaced 
    migration files are still around, the MigrationExecutor mark the squash 
    migration as unapplied, too, not only the replaced migrations."
    
    This is incorrect behavior. The squashed migration should remain applied
    if we are only unapplying the replaced ones, or the logic should correctly
    handle the state.
    """
    
    # We need to create a scenario with a squashed migration.
    # Since we cannot create files in the repo, we will simulate this by
    # using Django's internal test apps if available, or by creating a 
    # minimal in-memory migration structure.
    
    # However, Django's test suite has specific apps for testing migrations.
    # Let's try to use 'migration_test_app' or similar if it exists.
    # But the instructions say not to rely on test files.
    
    # Instead, let's look at the core logic. The issue is about 
    # MigrationExecutor.unapply_migrations().
    
    # Let's create a simple custom app with migrations programmatically.
    # This is complex. Let's try a different approach: inspect the code behavior
    # by creating a mock scenario using Django's migration framework directly.
    
    # Actually, the best way is to use an existing app that has squashed migrations.
    # Django's contenttypes or auth might have them, but they change between versions.
    
    # Let's try to reproduce the issue by creating a temporary app with squashed migrations.
    # We'll create a temporary directory for the app.
    
    temp_dir = tempfile.mkdtemp()
    app_name = 'test_squash_app'
    app_path = os.path.join(temp_dir, app_name)
    os.makedirs(app_path)
    
    # Create __init__.py
    with open(os.path.join(app_path, '__init__.py'), 'w') as f:
        f.write('')
    
    # Create models.py
    with open(os.path.join(app_path, 'models.py'), 'w') as f:
        f.write('''
from django.db import models

class MyModel(models.Model):
    name = models.CharField(max_length=100)
''')
    
    # Create migrations package
    migrations_path = os.path.join(app_path, 'migrations')
    os.makedirs(migrations_path)
    
    with open(os.path.join(migrations_path, '__init__.py'), 'w') as f:
        f.write('')
    
    # Create initial migration 0001_initial.py
    with open(os.path.join(migrations_path, '0001_initial.py'), 'w') as f:
        f.write('''
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='MyModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
    ]
''')
    
    # Create second migration 0002_add_field.py
    with open(os.path.join(migrations_path, '0002_add_field.py'), 'w') as f:
        f.write('''
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('test_squash_app', '0001_initial')]
    operations = [
        migrations.AddField(
            model_name='mymodel',
            name='description',
            field=models.TextField(blank=True),
        ),
    ]
''')
    
    # Create squashed migration 0001_squashed_0002.py
    with open(os.path.join(migrations_path, '0001_squashed_0002.py'), 'w') as f:
        f.write('''
from django.db import migrations, models

class Migration(migrations.Migration):
    replaces = [('test_squash_app', '0001_initial'), ('test_squash_app', '0002_add_field')]
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='MyModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
            ],
        ),
    ]
''')
    
    # Add the temp directory to sys.path so Django can find the app
    sys.path.insert(0, temp_dir)
    
    # Update INSTALLED_APPS
    if app_name not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS = list(settings.INSTALLED_APPS) + [app_name]
    
    # Reload Django setup to pick up new app
    # We need to clear the app registry and reload
    from django.apps import apps
    apps.clear_cache()
    
    # Re-initialize Django
    django.setup()
    
    try:
        # Create tables for the app
        executor = MigrationExecutor(connection)
        
        # Get the loader
        loader = executor.loader
        
        # Check that the squashed migration is recognized
        squashed_key = (app_name, '0001_squashed_0002')
        assert squashed_key in loader.graph.nodes, "Squashed migration not found in graph"
        
        # Apply all migrations
        executor.migrate([(app_name, None)])
        
        # Check that the squashed migration is recorded as applied
        recorder = MigrationRecorder(connection)
        applied_migrations = set(recorder.applied_migrations())
        
        # When a squashed migration is applied, it should be recorded as applied
        # and the replaced migrations should NOT be recorded as applied.
        assert squashed_key in applied_migrations, "Squashed migration should be applied"
        assert (app_name, '0001_initial') not in applied_migrations, "Replaced migration 0001 should not be applied"
        assert (app_name, '0002_add_field') not in applied_migrations, "Replaced migration 0002 should not be applied"
        
        # Now, simulate the scenario where we want to unapply the squashed migration.
        # The issue says: "When unapplying a squashed migration and the replaced 
        # migration files are still around, the MigrationExecutor mark the squash 
        # migration as unapplied, too, not only the replaced migrations."
        
        # Let's unapply to the initial state (before any migrations of this app)
        # This means we want to unapply the squashed migration.
        
        # First, let's record the current state
        before_unapply_applied = set(recorder.applied_migrations())
        assert squashed_key in before_unapply_applied
        
        # Unapply the squashed migration by targeting a state before it
        # We target an empty state for this app
        executor.unapply_migration(squashed_key)
        
        # After unapplying, check what is recorded
        after_unapply_applied = set(recorder.applied_migrations())
        
        # The squashed migration should now be unapplied (not in applied_migrations)
        # This is expected behavior when unapplying a squashed migration.
        
        # Wait, let me re-read the issue. 
        # "When unapplying a squashed migration and the replaced migration files 
        # are still around, the MigrationExecutor mark the squash migration as 
        # unapplied, too, not only the replaced migrations."
        
        # This suggests that when you unapply, BOTH the squashed AND the replaced
        # migrations are marked as unapplied. But the replaced migrations were never
        # applied in the first place (only the squashed one was). So marking them
        # as unapplied doesn't make sense because they weren't applied.
        
        # Actually, I think the issue is about a different scenario:
        # If you have a squashed migration applied, and then you want to "unapply" 
        # it to go back to the individual migrations (e.g., for development), 
        # the system might incorrectly mark the squashed migration as unapplied 
        # when it should keep track of the state properly.
        
        # Let me think again. The typical workflow:
        # 1. Apply squashed migration -> squashed is applied, replaced are not.
        # 2. Unapply squashed migration -> squashed should be unapplied.
        
        # But the issue mentions "the replaced migration files are still around".
        # This might refer to a case where you have both the squashed and the 
        # individual migrations in your migrations folder.
        
        # Let's check if after unapplying the squashed migration, the system 
        # tries to do something weird with the replaced migrations.
        
        # Actually, looking at Django's code, when you unapply a squashed migration,
        # it should just unapply the operations in the squashed migration.
        
        # The bug might be that when checking which migrations are applied, 
        # the system incorrectly considers the squashed migration as unapplied 
        # even though it was applied, due to some logic error.
        
        # Let me re-interpret: Perhaps the issue is that after applying a squashed 
        # migration, if you query the migration state, it might incorrectly show 
        # the squashed migration as unapplied under certain conditions.
        
        # Let's check the loader's applied status after applying.
        loader.build_graph()
        
        # Re-apply to ensure clean state
        executor.migrate([(app_name, None)])
        
        # Check applied status via loader
        plan = executor.migration_plan(loader.graph.leaf_nodes())
        # plan should be empty since everything is applied
        
        # Now let's check if the squashed migration is considered applied by the loader
        # The loader has a method `applied_migrations` or we can check the graph
        
        # Let's look at the actual bug more carefully. The title says:
        # "Squashed migration is not marked as unapplied"
        
        # Wait, the title says "NOT marked as unapplied". So the bug is that 
        # when it SHOULD be marked as unapplied, it is NOT.
        
        # Let me re-read the description:
        # "When unapplying a squashed migration and the replaced migration files 
        # are still around, the MigrationExecutor mark the squash migration as 
        # unapplied, too, not only the replaced migrations."
        
        # This is confusing. Let me parse it:
        # - We are unapplying a squashed migration.
        # - The replaced migration files are still around.
        # - The MigrationExecutor marks the squashed migration as unapplied.
        # - It also marks the replaced migrations as unapplied.
        
        # The phrase "too, not only" suggests that marking the squashed as 
        # unapplied is unexpected/wrong, and only the replaced ones should be 
        # affected? Or vice versa?
        
        # Actually, I think the correct interpretation is:
        # When you unapply a squashed migration, ONLY the squashed migration 
        # should be marked as unapplied. The replaced migrations were never 
        # applied, so they shouldn't be touched. But the bug is that BOTH are 
        # marked as unapplied.
        
        # Hmm, but if the replaced migrations were never applied, marking them 
        # as unapplied is a no-op or an error.
        
        # Let me look at this from another angle. Perhaps the issue is about 
        # the reverse: when you have a squashed migration applied, and you 
        # check which migrations are applied, the squashed migration is NOT 
        # shown as applied (i.e., it's incorrectly shown as unapplied).
        
        # The title "Squashed migration is not marked as unapplied" could mean:
        # - Expected: squashed migration should be marked as unapplied (after unapply)
        # - Actual: it is NOT marked as unapplied (bug)
        
        # OR it could mean:
        # - The squashed migration is incorrectly NOT marked as unapplied when it should be.
        
        # Given the ambiguity, let's look at what the fix would be. In Django,
        # there was a bug where squashed migrations were not properly tracked.
        
        # Let's test a specific scenario: after applying a squashed migration,
        # is it correctly recorded as applied?
        
        executor.migrate([(app_name, None)])
        applied = set(MigrationRecorder(connection).applied_migrations())
        
        # The squashed migration should be in applied
        assert squashed_key in applied, f"Squashed migration {squashed_key} should be applied but applied migrations are: {applied}"
        
        # The replaced migrations should NOT be in applied
        assert (app_name, '0001_initial') not in applied
        assert (app_name, '0002_add_field') not in applied
        
        # Now unapply the squashed migration
        executor.unapply_migration(squashed_key)
        
        applied_after = set(MigrationRecorder(connection).applied_migrations())
        
        # After unapplying, the squashed migration should NOT be in applied
        assert squashed_key not in applied_after, f"Squashed migration {squashed_key} should be unapplied but applied migrations are: {applied_after}"
        
        # This is the correct behavior. If this assertion passes, the bug is fixed.
        # If it fails (i.e., squashed_key is still in applied_after), then the 
        # squashed migration is NOT marked as unapplied, which is the bug.
        
        print("Test passed: Squashed migration is correctly marked as unapplied after unapply.")
        
    finally:
        # Cleanup
        sys.path.remove(temp_dir)
        shutil.rmtree(temp_dir)
        
        # Remove the app from INSTALLED_APPS
        if app_name in settings.INSTALLED_APPS:
            settings.INSTALLED_APPS = [app for app in settings.INSTALLED_APPS if app != app_name]
        
        # Clear cache again
        from django.apps import apps
        apps.clear_cache()


if __name__ == '__main__':
    test_squashed_migration_unapply_behavior()
