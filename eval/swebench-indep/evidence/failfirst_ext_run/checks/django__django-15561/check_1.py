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

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db import models
from django.apps import apps
from django.db.migrations.state import ProjectState
from django.db.migrations.operations import AlterField

def main():
    # We need to simulate a migration operation that changes choices on a field.
    # The issue states that on SQLite, adding/changing choices generates SQL 
    # (recreating the table), whereas it should be a noop (no SQL generated) 
    # because choices are not enforced at the database level.

    # To test this directly without creating actual migration files on disk,
    # we can use the MigrationExecutor and manually construct the operations.
    
    # 1. Create a simple model state with a field that has no choices.
    # 2. Create a new model state with the same field but with choices added.
    # 3. Generate the SQL for the AlterField operation between these two states.
    # 4. Check if any SQL is generated. If SQL is generated, the bug exists (exit non-zero).
    #    If no SQL is generated, the bug is fixed (exit 0).

    # However, testing via MigrationExecutor with real tables is more robust.
    # Let's define a temporary app label for our test models.
    
    app_label = 'test_choices_app'
    
    # Ensure the app registry is ready
    from django.core.management import call_command
    
    # We will create a model, migrate it, then try to alter the field to add choices.
    # We'll capture the SQL executed during the migration.
    
    # Define Model 1: No choices
    class Author(models.Model):
        name = models.CharField(max_length=100)
        
        class Meta:
            app_label = app_label
            
    # Define Model 2: With choices (same structure, just different field definition)
    class AuthorWithChoices(models.Model):
        CHOICES = [
            ('A', 'Choice A'),
            ('B', 'Choice B'),
        ]
        name = models.CharField(max_length=100, choices=CHOICES)
        
        class Meta:
            app_label = app_label
            db_table = 'test_choices_app_author' # Same table name

    # We need to interact with the schema editor directly to see what SQL it produces.
    # The most direct way is to use the SchemaEditor associated with the connection.
    
    # Get the current project state and prepare a fake migration context
    executor = MigrationExecutor(connection)
    
    # Let's create the initial table first using the standard migrate command logic 
    # but simplified for this script.
    
    # Instead of full migrations, let's look at how `AlterField` behaves in isolation.
    # We can instantiate a SchemaEditor and call `alter_field`.
    
    # First, create the table for the model without choices.
    with connection.schema_editor() as schema_editor:
        # Create the initial model
        schema_editor.create_model(Author)
        
    # Now, let's capture SQL when altering the field to add choices.
    # We need to compare the old field and the new field.
    
    old_field = Author._meta.get_field('name')
    new_field = AuthorWithChoices._meta.get_field('name')
    
    # Capture SQL statements
    collected_sql = []
    
    class SQLCollectorSchemaEditor(connection.ops.schema_editor_class):
        def execute(self, sql, params=()):
            if sql:
                collected_sql.append(str(sql))
            super().execute(sql, params)
            
        def __enter__(self):
            super().__enter__()
            return self
            
        def __exit__(self, exc_type, exc_value, traceback):
            return super().__exit__(exc_type, exc_value, traceback)

    # Use the custom schema editor to capture SQL
    with SQLCollectorSchemaEditor(connection, collect_sql=False) as schema_editor:
        schema_editor.alter_field(Author, old_field, new_field, strict=True)
        
    # Drop the table afterwards to clean up (though it's in memory)
    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(Author)

    # Analyze the collected SQL
    # If the bug is present, collected_sql will contain CREATE TABLE, INSERT, DROP TABLE, etc.
    # If the bug is fixed, collected_sql should be empty or only contain comments/no-ops.
    
    # Filter out any potential empty strings or whitespace-only entries
    significant_sql = [s for s in collected_sql if s.strip()]
    
    print(f"Collected SQL statements: {significant_sql}")
    
    # Assertion: If significant SQL was generated, the behavior is WRONG (bug exists).
    # We want the script to exit 0 if FIXED (no SQL), and non-zero if WRONG (SQL exists).
    # Therefore, we assert that significant_sql is EMPTY.
    
    assert len(significant_sql) == 0, f"Expected no SQL for adding choices on SQLite, but got: {significant_sql}"

if __name__ == '__main__':
    main()
