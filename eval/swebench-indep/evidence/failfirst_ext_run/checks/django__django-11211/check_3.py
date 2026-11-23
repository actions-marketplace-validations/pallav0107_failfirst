import os
import sys
import uuid
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
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.core.management.color import no_style

# Define models dynamically
class Foo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default="test")

    class Meta:
        app_label = 'test_app'

class Bar(models.Model):
    foo_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='actor'
    )
    foo_object_id = models.CharField(max_length=255)
    foo = GenericForeignKey('foo_content_type', 'foo_object_id')

    class Meta:
        app_label = 'test_app'

# Create tables
def create_tables():
    with connection.schema_editor() as schema_editor:
        # Create ContentType table first as it's required by GFK
        from django.contrib.contenttypes.models import ContentType
        schema_editor.create_model(ContentType)
        
        # Create our test models
        schema_editor.create_model(Foo)
        schema_editor.create_model(Bar)

create_tables()

# Test the issue
def test_prefetch_related_gfk_uuid():
    # Create a Foo instance with UUID PK
    foo_instance = Foo.objects.create(name="Test Foo")
    
    # Create a Bar instance pointing to the Foo instance via GFK
    bar_instance = Bar.objects.create(
        foo_content_type=ContentType.objects.get_for_model(Foo),
        foo_object_id=str(foo_instance.id),
    )
    
    # Query with prefetch_related
    bars = Bar.objects.all().prefetch_related('foo')
    
    # Check if prefetch worked correctly
    for bar in bars:
        # Access the GFK field
        fetched_foo = bar.foo
        
        # The issue states that django orm engine returns None for attribute foo
        # If fixed, it should return the correct Foo instance
        assert fetched_foo is not None, "Prefetch related returned None for GFK with UUID PK"
        assert fetched_foo.id == foo_instance.id, f"Expected {foo_instance.id}, got {fetched_foo.id}"
        assert fetched_foo.name == "Test Foo", f"Expected 'Test Foo', got {fetched_foo.name}"

if __name__ == '__main__':
    try:
        test_prefetch_related_gfk_uuid()
        print("Test passed: Prefetch related works correctly with GFK and UUID PK")
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
