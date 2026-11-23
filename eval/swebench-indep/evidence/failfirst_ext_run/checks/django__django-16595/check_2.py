import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_settings')
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

from django.db import migrations
from django.db.migrations.optimizer import MigrationOptimizer
from django.db.models.fields import CharField

def test_alter_field_reduction():
    """
    Test that multiple AlterField operations on the same field are reduced
    to a single AlterField operation.
    """
    # Create a series of AlterField operations
    operations = [
        migrations.AlterField(
            model_name="book",
            name="title",
            field=CharField(max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name="book",
            name="title",
            field=CharField(max_length=128, null=True, help_text="help"),
        ),
        migrations.AlterField(
            model_name="book",
            name="title",
            field=CharField(max_length=128, null=True, help_text="help", default=None),
        ),
    ]

    optimizer = MigrationOptimizer()
    
    # Optimize the operations
    optimized_operations = optimizer.optimize(operations, "books")
    
    # The issue states that currently none of the AlterField are reduced.
    # If the bug is fixed, these three AlterField operations should be reduced
    # to a single AlterField operation (the last one, as it contains all changes).
    
    # Check if the optimization reduced the operations correctly
    # We expect exactly 1 operation after optimization if the bug is fixed
    assert len(optimized_operations) == 1, f"Expected 1 optimized operation, got {len(optimized_operations)}: {optimized_operations}"
    
    # Verify it's an AlterField operation
    assert isinstance(optimized_operations[0], migrations.AlterField), f"Expected AlterField, got {type(optimized_operations[0])}"
    
    # Verify the final field has all the accumulated changes
    final_op = optimized_operations[0]
    assert final_op.name == "title"
    assert final_op.model_name == "book"
    
    # The final field should have max_length=128, null=True, help_text="help", default=None
    final_field = final_op.field
    assert final_field.max_length == 128, f"Expected max_length=128, got {final_field.max_length}"
    assert final_field.null == True, f"Expected null=True, got {final_field.null}"
    assert final_field.help_text == "help", f"Expected help_text='help', got {final_field.help_text}"
    assert final_field.default is None, f"Expected default=None, got {final_field.default}"

if __name__ == "__main__":
    try:
        test_alter_field_reduction()
        print("Test passed: AlterField reduction is working correctly.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
