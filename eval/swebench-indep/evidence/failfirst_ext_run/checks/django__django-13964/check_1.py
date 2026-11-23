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
from django.db.utils import ConnectionHandler

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

def test_issue():
    """
    Test the specific bug reported:
    Saving parent object after setting on child leads to data loss for parents with non-numeric primary key.
    """
    with transaction.atomic():
        order = Order()
        # Initialize relation with an empty instance that does not yet specify its primary key
        order.product = Product()
        # Subsequently define the primary key
        order.product.sku = "foo"
        # Save the child (product)
        order.product.save()
        
        # At this point, order.product_id should be updated to reflect order.product.sku ("foo")
        # If the bug exists, order.product_id remains "" because it was set when product.sku was empty/None
        
        # Save the parent (order)
        order.save()
        
        # Check if the order correctly references the product with sku "foo"
        # The bug causes order.product_id to be "", so this filter would fail to find the order
        # or find an order linked to a non-existent product "" (which fails FK constraint on commit if not deferred)
        
        # Assert that the order can be found via the product relationship
        assert Order.objects.filter(product=order.product).exists(), \
            "Order should be linked to the product with sku 'foo', but it is not."
            
        # Also explicitly check the product_id value
        order.refresh_from_db()
        assert order.product_id == "foo", \
            f"Order.product_id should be 'foo', but got '{order.product_id}'"

if __name__ == '__main__':
    try:
        test_issue()
        print("Test passed: Issue is fixed.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: Issue still exists. Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
