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
from django import forms

# Define models to reproduce the issue
class Author(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class Book(models.Model):
    title = models.CharField(max_length=100)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    class Meta:
        app_label = 'test_app'

class Publisher(models.Model):
    name = models.CharField(max_length=100)
    books = models.ManyToManyField(Book)

    class Meta:
        app_label = 'test_app'

class Article(models.Model):
    headline = models.CharField(max_length=100)
    # This ForeignKey uses limit_choices_to with a Q object involving a join
    # via the ManyToMany relationship from Publisher to Book to Author.
    # We want to limit authors to those who have books published by a specific publisher.
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(book__publisher__name='Test Publisher')
    )

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Author)
    schema_editor.create_model(Book)
    schema_editor.create_model(Publisher)
    schema_editor.create_model(Article)

# Create test data
# Create an author
author = Author.objects.create(name='John Doe')

# Create a publisher
publisher = Publisher.objects.create(name='Test Publisher')

# Create a book linking the author and publisher
book = Book.objects.create(title='Some Book', author=author)
publisher.books.add(book)

# Create another book for the same author and publisher to potentially cause duplicates
# if the query isn't distinct
book2 = Book.objects.create(title='Another Book', author=author)
publisher.books.add(book2)

# Now check the form field for Article.author
class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['headline', 'author']

form = ArticleForm()
author_field = form.fields['author']

# Get the choices
choices = list(author_field.queryset.values_list('pk', flat=True))

# The issue is that duplicate options appear in the form.
# If the bug exists, the queryset will return the same author multiple times
# because of the join with the intermediate table (Book-Publisher).
# If fixed, the queryset should be distinct, so each author appears only once.

# We expect only one author (John Doe) to be in the choices.
# If there are duplicates, len(choices) will be > 1 or the set size will be less than list size.
# Actually, ModelChoiceField uses a queryset. If the queryset has duplicates, 
# the widget might show them multiple times depending on how it's rendered, 
# but typically the queryset itself should be distinct.

# Let's check the count of the queryset vs the distinct count.
qs_count = author_field.queryset.count()
qs_distinct_count = author_field.queryset.distinct().count()

# If the bug is present, qs_count might be > qs_distinct_count due to joins.
# However, Django's ModelChoiceField usually iterates over the queryset.
# Let's look at the actual values returned.
all_authors_in_qs = list(author_field.queryset)
unique_authors_in_qs = set(all_authors_in_qs)

# Assert that there are no duplicates in the queryset provided to the form field.
# If the bug is fixed, the queryset should effectively be distinct.
assert len(all_authors_in_qs) == len(unique_authors_in_qs), \
    f"Duplicate authors found in formfield choices: {len(all_authors_in_qs)} items but only {len(unique_authors_in_qs)} unique. Choices: {[a.name for a in all_authors_in_qs]}"

# Also verify that the correct author is present
assert author in unique_authors_in_qs, "The expected author was not found in the choices."

print("Check passed: No duplicate options in formfield.")
sys.exit(0)
