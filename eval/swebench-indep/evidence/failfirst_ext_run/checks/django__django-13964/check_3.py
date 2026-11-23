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

from django.db import models, connection, transaction

# Define models dynamically
class Product(models.Model):
    sku = models.CharField(primary_key=True, max_length=50)

    class Meta:
        app_label = 'test_app'

class Order(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Product)
    schema_editor.create_model(Order)

def test_bug_fix():
    """
    Test that saving a parent object after setting the primary key on a child
    object (which was initially empty) correctly updates the foreign key reference.
    """
    with transaction.atomic():
        order = Order()
        # Initialize with an empty instance
        order.product = Product()
        # Set the primary key afterwards
        order.product.sku = "foo"
        # Save the child
        order.product.save()
        # Save the parent
        order.save()
        
        # Refresh from database to ensure we are checking persisted state
        order.refresh_from_db()
        
        # The bug was that order.product_id was "" instead of "foo"
        # If fixed, order.product_id should be "foo"
        assert order.product_id == "foo", f"Expected product_id to be 'foo', but got '{order.product_id}'"
        
        # Also verify the relationship works correctly
        assert Order.objects.filter(product=order.product).exists(), "Order should be linked to the product"
        
        # Verify the incorrect behavior does not exist
        assert not Order.objects.filter(product_id="").exists(), "No order should have an empty product_id"

if __name__ == '__main__':
    try:
        test_bug_fix()
        print("Test passed: Bug is fixed.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during test: {e}")
        sys.exit(1)
