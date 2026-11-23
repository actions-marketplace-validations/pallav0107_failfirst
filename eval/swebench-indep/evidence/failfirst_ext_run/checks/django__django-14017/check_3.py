import os
import sys
import django

# Configure Django settings for an in-memory SQLite database
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

if not django.conf.settings.configured:
    django.conf.settings.configure(
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
    )

django.setup()

from django.db import models
from django.db.models import Q, Exists

# Define a simple model to use with Exists
class Product(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

# Create the table
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Product)

# Test the issue: Q(...) & Exists(...) should work just like Exists(...) & Q(...)
try:
    # This works according to the issue description
    expr1 = Exists(Product.objects.all()) & Q()
    
    # This raises TypeError in the buggy version
    expr2 = Q() & Exists(Product.objects.all())
    
    # If we reach here, the TypeError was not raised, which means the fix is present.
    # We assert that both expressions are valid and can be combined.
    assert expr1 is not None
    assert expr2 is not None
    
    print("Success: Q() & Exists(...) does not raise TypeError.")
    sys.exit(0)

except TypeError as e:
    print(f"Failure: TypeError raised: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
