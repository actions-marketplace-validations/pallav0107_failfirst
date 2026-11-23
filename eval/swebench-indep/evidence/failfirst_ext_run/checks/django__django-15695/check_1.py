import os
import sys
import django
from django.conf import settings

# Configure Django settings for an in-memory SQLite database
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

from django.db import connection, models
from django.db.migrations.state import ProjectState
from django.db.migrations.operations.models import RenameIndex
from django.db.migrations.executor import MigrationExecutor

# Define a simple model to test index renaming
class TestModel(models.Model):
    name = models.CharField(max_length=100)
    value = models.IntegerField()

    class Meta:
        app_label = 'test_app'
        unique_together = [('name', 'value')]

def main():
    # Create the table initially
    with connection.schema_editor() as editor:
        editor.create_model(TestModel)

    # Get the initial state
    project_state = ProjectState.from_apps([TestModel._meta.app_config])
    
    # We need to simulate the scenario described:
    # 1. An unnamed index (auto-generated from unique_together) exists.
    # 2. RenameIndex is applied forward (giving it a new name).
    # 3. RenameIndex is applied backward (restoring the old auto-generated name).
    # 4. RenameIndex is applied forward AGAIN. This is where it crashes if not fixed.

    # Let's find the actual name of the auto-generated index
    table_name = TestModel._meta.db_table
    with connection.cursor() as cursor:
        # SQLite specific query to get index names
        cursor.execute(f"PRAGMA index_list('{table_name}')")
        indexes = cursor.fetchall()
        
    # Find the unique index created by unique_together
    # In SQLite, auto-generated indexes for unique_together usually have names like 
    # test_app_testmodel_name_value_... or similar depending on version.
    # However, Django's RenameIndex operation logic handles the "old_name" detection.
    
    # To strictly follow the issue, we rely on Django's internal state management.
    # The issue states that re-applying RenameIndex crashes because it tries to create 
    # an index that already exists (or rename to a name that conflicts).
    
    # Let's construct the migration operations manually.
    
    # Step 1: Initial State
    initial_state = ProjectState.from_apps([TestModel._meta.app_config])
    
    # Get the real index name from the database state
    # Django's BaseDatabaseSchemaEditor._get_index_sql_name or similar internals 
    # determine the auto-generated name.
    # For SQLite, let's just look at what Django thinks the index name is.
    
    # Actually, it's easier to use the migration framework's logic.
    # The auto-generated index name for unique_together in Django is typically derived.
    # Let's assume the standard naming convention or retrieve it.
    
    # Retrieve the current index name from the project state
    model_state = initial_state.models['test_app', 'testmodel']
    # The index is part of the unique_together constraint, which creates an implicit index.
    # In Django 4.1+, these are represented as Index objects in the state if they are explicit,
    # but unique_together creates constraints.
    
    # Let's look at how RenameIndex works. It takes old_name and new_name.
    # If the index was auto-generated, old_name is the auto-generated one.
    
    # We need to know the auto-generated name.
    # In Django, for SQLite, the index name for unique_together ('name', 'value') 
    # is typically 'test_app_testmodel_name_value_idx' or similar.
    
    # Let's try to get the exact name from the database
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}'")
        all_indexes = [row[0] for row in cursor.fetchall()]
        
    # Filter for the unique index related to our columns
    target_index_name = None
    for idx_name in all_indexes:
        if 'name' in idx_name and 'value' in idx_name:
            target_index_name = idx_name
            break
            
    if target_index_name is None:
        print("Could not find the auto-generated index.")
        sys.exit(1)

    print(f"Found auto-generated index: {target_index_name}")
    
    new_index_name = "new_pony_test_idx"
    
    # Create the RenameIndex operation
    operation = RenameIndex(
        model_name='TestModel',
        new_name=new_index_name,
        old_name=target_index_name,
    )
    
    # Simulate the sequence: Forward -> Backward -> Forward
    
    # 1. Forward
    new_state = initial_state.clone()
    with connection.schema_editor() as editor:
        operation.database_forwards('test_app', editor, initial_state, new_state)
        
    # Verify the index was renamed
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}'")
        indexes_after_forward = [row[0] for row in cursor.fetchall()]
        
    assert new_index_name in indexes_after_forward, f"Index {new_index_name} not found after forward migration."
    assert target_index_name not in indexes_after_forward, f"Old index {target_index_name} still exists after forward migration."
    
    # 2. Backward
    prev_state = initial_state.clone() # The state before the forward op
    with connection.schema_editor() as editor:
        operation.database_backwards('test_app', editor, new_state, prev_state)
        
    # Verify the index was renamed back
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}'")
        indexes_after_backward = [row[0] for row in cursor.fetchall()]
        
    assert target_index_name in indexes_after_backward, f"Index {target_index_name} not found after backward migration."
    assert new_index_name not in indexes_after_backward, f"New index {new_index_name} still exists after backward migration."
    
    # 3. Forward Again (This is the crash point in the bug)
    # We need a fresh clone of the state representing the "before" state for this second forward
    state_before_second_forward = prev_state.clone()
    state_after_second_forward = new_state.clone()
    
    try:
        with connection.schema_editor() as editor:
            operation.database_forwards('test_app', editor, state_before_second_forward, state_after_second_forward)
    except Exception as e:
        print(f"Crash occurred during second forward migration: {e}")
        sys.exit(1)
        
    # Verify the index is correctly named again
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}'")
        indexes_final = [row[0] for row in cursor.fetchall()]
        
    assert new_index_name in indexes_final, f"Index {new_index_name} not found after second forward migration."
    
    print("Success: RenameIndex handled forward-backward-forward cycle correctly.")
    sys.exit(0)

if __name__ == '__main__':
    main()
