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
from django.db.migrations.optimizer import MigrationOptimizer

def test_alter_field_optimization():
    """
    Test that multiple consecutive AlterField operations on the same field
    are reduced to a single AlterField operation by the optimizer.
    """
    
    # Create a sequence of AlterField operations
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
    
    # Optimize the operations
    optimized_operations = optimizer.optimize(operations, "books")
    
    # The expected behavior is that multiple AlterField operations on the same field
    # should be reduced to just the last one (since it contains all the cumulative changes)
    # So we expect only 1 operation in the result
    
    print(f"Original operations count: {len(operations)}")
    print(f"Optimized operations count: {len(optimized_operations)}")
    
    for i, op in enumerate(optimized_operations):
        print(f"  Optimized op {i}: {op}")
        
    # Assert that the optimization reduced the operations to a single AlterField
    assert len(optimized_operations) == 1, f"Expected 1 optimized operation, got {len(optimized_operations)}"
    
    # Assert that the remaining operation is an AlterField
    assert isinstance(optimized_operations[0], migrations.AlterField), \
        f"Expected AlterField, got {type(optimized_operations[0])}"
    
    # Assert that the final field has all the cumulative properties from the last AlterField
    final_op = optimized_operations[0]
    assert final_op.model_name == "book"
    assert final_op.name == "title"
    assert final_op.field.max_length == 128
    assert final_op.field.null is True
    assert final_op.field.help_text == "help"
    assert final_op.field.default is None
    
    print("Test passed: Multiple AlterField operations were correctly optimized.")

if __name__ == "__main__":
    try:
        test_alter_field_optimization()
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
