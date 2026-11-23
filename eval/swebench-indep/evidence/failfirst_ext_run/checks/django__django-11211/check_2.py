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
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
    )

django.setup()

from django.db import models, connection
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
import uuid

# Define models dynamically to avoid needing a separate app
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
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(ContentType)
    schema_editor.create_model(Foo)
    schema_editor.create_model(Bar)

# Create test data
foo_instance = Foo.objects.create(name="Test Foo")
content_type = ContentType.objects.get_for_model(Foo)

# Note: UUIDs are stored as strings in CharField for GFK object_id
bar_instance = Bar.objects.create(
    foo_content_type=content_type,
    foo_object_id=str(foo_instance.id)
)

# Test prefetch_related
# The issue states that prefetch_related returns None for the GFK attribute
# when the target model uses a UUID PK.

bars = Bar.objects.all().prefetch_related('foo')

found_bar = None
for b in bars:
    found_bar = b
    break

assert found_bar is not None, "No Bar instance found"

# Access the prefetched GFK attribute
fetched_foo = found_bar.foo

# If the bug is present, fetched_foo will be None because the lookup failed
# due to type mismatch or improper handling of UUID in GFK prefetching.
assert fetched_foo is not None, "Prefetch related failed: foo is None"

# Verify it's the correct object
assert fetched_foo.id == foo_instance.id, "Fetched foo ID does not match"
assert fetched_foo.name == "Test Foo", "Fetched foo name does not match"

print("Test passed: Prefetch related works correctly with UUID PK and GFK.")
sys.exit(0)
