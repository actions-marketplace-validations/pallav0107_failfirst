import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

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
from django.db.utils import OperationalError

# Define models dynamically to avoid file creation
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

def test_issue():
    """
    Test case for: Saving parent object after setting on child leads to data loss 
    for parents with non-numeric primary key.
    """
    with transaction.atomic():
        order = Order()
        # Initialize relation with an empty instance that does not yet specify its primary key
        order.product = Product()
        # Subsequently define the primary key
        order.product.sku = "foo"
        # Save the parent (product)
        order.product.save()
        # Save the child (order)
        order.save()
        
        # The issue states that order.product_id becomes "" instead of "foo"
        # If fixed, order.product_id should be "foo"
        
        # Check if the order correctly references the product with sku "foo"
        # The bug causes Order.objects.filter(product_id="").exists() to succeed (wrong)
        # and Order.objects.filter(product=order.product).exists() to fail (wrong)
        
        # Refresh from DB to ensure we are checking persisted state
        order.refresh_from_db()
        
        # Assert that the foreign key ID is correctly set to "foo", not ""
        assert order.product_id == "foo", f"Expected product_id to be 'foo', but got '{order.product_id}'"
        
        # Assert that we can filter by the product instance
        assert Order.objects.filter(product=order.product).exists(), "Order should be filterable by its product instance"
        
        # Assert that there is NO order with empty product_id
        assert not Order.objects.filter(product_id="").exists(), "There should be no order with empty product_id"

if __name__ == '__main__':
    try:
        test_issue()
        print("Test passed: Issue is fixed.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: Issue still exists. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
