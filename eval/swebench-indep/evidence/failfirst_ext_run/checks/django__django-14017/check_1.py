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

from django.db import models
from django.db.models import Q, Exists

# Define a simple model for testing
class Product(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

# Create the table
from django.core.management import call_command
from django.db import connection

with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Product)

# Test the issue: Q(...) & Exists(...) should work just like Exists(...) & Q(...)
try:
    # This should not raise TypeError
    q_exists = Q() & Exists(Product.objects.all())
    
    # Verify it returns a valid Q object or combined expression
    assert q_exists is not None
    
    # Also test the reverse to ensure commutativity works both ways
    exists_q = Exists(Product.objects.all()) & Q()
    assert exists_q is not None
    
    # If we reach here, the bug is fixed
    print("Test passed: Q() & Exists(...) works correctly.")
    sys.exit(0)
    
except TypeError as e:
    print(f"Test failed: TypeError raised - {e}")
    sys.exit(1)
except Exception as e:
    print(f"Test failed with unexpected error: {e}")
    sys.exit(1)
