import os
import sys
import django

# Configure Django settings for an in-memory SQLite database
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
        SECRET_KEY='test-secret-key-for-check-script-only',
    )

django.setup()

from django.db import models
from django.db.models import Q, Exists

# Define a simple model to use with Exists
class Product(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

# Create the table in memory
from django.db import connection
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Product)

# Test the issue: Q(...) & Exists(...) should work just like Exists(...) & Q(...)
# The issue states that Exists(...) & Q(...) works, but Q(...) & Exists(...) raises TypeError.
# If fixed, both should work and produce equivalent results.

try:
    exists_expr = Exists(Product.objects.all())
    q_obj = Q(id=1)

    # This is reported to work
    result1 = exists_expr & q_obj
    
    # This is reported to raise TypeError
    result2 = q_obj & exists_expr
    
    # If we reach here, the TypeError is fixed.
    # We can also check if they are logically equivalent or at least valid objects.
    # The primary fix is that it doesn't crash.
    
    print("Success: Q() & Exists() did not raise TypeError.")
    sys.exit(0)

except TypeError as e:
    print(f"Failure: Q() & Exists() raised TypeError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
