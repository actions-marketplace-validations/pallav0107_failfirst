import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

# Minimal settings configuration if not already present
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
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

from django.db import connection, models
from django.db.models import Value

# Define minimal models to reproduce the issue
class Publisher(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class Book(models.Model):
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    pages = models.IntegerField()

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Publisher)
    schema_editor.create_model(Book)

# Insert test data
p1 = Publisher.objects.create(name='Apress')
p2 = Publisher.objects.create(name='Sams')
p3 = Publisher.objects.create(name='Prentice Hall')
p4 = Publisher.objects.create(name='Morgan Kaufmann')
p5 = Publisher.objects.create(name='Other Publisher')

Book.objects.create(publisher=p1, pages=500)
Book.objects.create(publisher=p2, pages=600)
Book.objects.create(publisher=p3, pages=450)
Book.objects.create(publisher=p4, pages=800)
Book.objects.create(publisher=p5, pages=300) # Should be excluded (pages <= 400)

# Reproduce the bug scenario
def test_annotation_and_alias_filter_in_subquery():
    long_books_qs = (
        Book.objects.filter(
            pages__gt=400,
        )
        .annotate(book_annotate=Value(1))
        .alias(book_alias=Value(1))
    )
    
    # This query should work without raising OperationalError
    # The bug causes the subquery to return all columns instead of just the PK
    # because __in doesn't clear selected fields when alias() is used after annotate()
    publisher_books_qs = (
        Publisher.objects.filter(
            book__in=long_books_qs
        )
        .values("name")
    )
    
    # Execute the query to trigger any SQL errors
    result = list(publisher_books_qs)
    
    expected = [
        {'name': 'Apress'},
        {'name': 'Sams'},
        {'name': 'Prentice Hall'},
        {'name': 'Morgan Kaufmann'}
    ]
    
    # Sort for consistent comparison since assertCountEqual isn't available directly on lists
    # but we can sort the dicts by name
    result_sorted = sorted(result, key=lambda x: x['name'])
    expected_sorted = sorted(expected, key=lambda x: x['name'])
    
    assert result_sorted == expected_sorted, f"Expected {expected_sorted}, got {result_sorted}"

if __name__ == '__main__':
    try:
        test_annotation_and_alias_filter_in_subquery()
        print("Test passed: Issue is fixed.")
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
