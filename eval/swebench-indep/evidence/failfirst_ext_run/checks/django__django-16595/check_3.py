import os
import sys

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
        SECRET_KEY='test-secret-key-for-check-script-only',
    )

django.setup()

from django.db import migrations, models
from django.db.migrations.optimizer import MigrationOptimizer


def main():
    # Create the operations as described in the issue
    # We are specifically testing the optimization of multiple AlterField operations
    # on the same field.
    
    operations = [
        migrations.AlterField(
            model_name="book",
            name="title",
            field=models.CharField(max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name="book",
            name="title",
            field=models.CharField(max_length=128, null=True, help_text="help"),
        ),
        migrations.AlterField(
            model_name="book",
            name="title",
            field=models.CharField(max_length=128, null=True, help_text="help", default=None),
        ),
    ]

    optimizer = MigrationOptimizer()
    
    # Optimize the list of AlterField operations
    optimized_operations = optimizer.optimize(operations, "books")
    
    # The issue states that currently none of the AlterField are reduced.
    # The expected correct behavior (the fix) is that consecutive AlterField 
    # operations on the same field should be reduced to just the last one,
    # because the last one supersedes the previous ones.
    
    # So, if the bug is fixed, optimized_operations should contain only 1 operation.
    # If the bug is present, it will contain 3 operations.
    
    print(f"Number of original operations: {len(operations)}")
    print(f"Number of optimized operations: {len(optimized_operations)}")
    
    for i, op in enumerate(optimized_operations):
        print(f"Optimized op {i}: {op}")

    # Assert that the optimization reduced the operations to a single AlterField
    assert len(optimized_operations) == 1, (
        f"Expected 1 optimized operation, but got {len(optimized_operations)}. "
        "The migration optimizer should reduce multiple AlterField operations "
        "on the same field to just the last one."
    )
    
    # Verify it is an AlterField
    assert isinstance(optimized_operations[0], migrations.AlterField), (
        "Expected the remaining operation to be an AlterField."
    )
    
    # Verify it is the last one (with default=None and help_text="help")
    final_op = optimized_operations[0]
    assert final_op.name == "title"
    assert final_op.model_name == "book"
    
    # Check specific attributes of the field to ensure it's the last one
    field = final_op.field
    assert field.max_length == 128
    assert field.null is True
    assert field.help_text == "help"
    assert field.default is None
    
    print("Check passed: Migration optimizer correctly reduces multiple AlterField operations.")
    sys.exit(0)


if __name__ == "__main__":
    main()
