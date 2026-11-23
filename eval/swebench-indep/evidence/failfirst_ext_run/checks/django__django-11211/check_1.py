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

from django.db import models, connection
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
import uuid

# Define models dynamically to avoid file creation
class Foo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class Bar(models.Model):
    foo_content_type = models.ForeignKey(
        ContentType, related_name='actor',
        on_delete=models.CASCADE, db_index=True
    )
    foo_object_id = models.CharField(max_length=255, db_index=True)
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
bar_instance = Bar.objects.create(foo_content_type=ContentType.objects.get_for_model(Foo), foo_object_id=str(foo_instance.id))

# Test prefetch_related
bars = Bar.objects.all().prefetch_related('foo')
for bar in bars:
    # Access the generic foreign key
    fetched_foo = bar.foo
    # Check if it is None (the bug) or the correct instance
    assert fetched_foo is not None, "Prefetch related returned None for GFK with UUID PK"
    assert fetched_foo.id == foo_instance.id, "Prefetch related returned wrong instance"

print("Test passed: Prefetch related works correctly for GFK with UUID PK.")
sys.exit(0)
