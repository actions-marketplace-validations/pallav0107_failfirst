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
from django.forms import ModelForm

# Define models to reproduce the issue
class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'test_app'

class Article(models.Model):
    title = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    class Meta:
        app_label = 'test_app'

class Author(models.Model):
    name = models.CharField(max_length=100)
    # This ForeignKey uses limit_choices_to with a Q object involving a join
    # We want to limit authors to those who have written articles in a specific category
    # But if the query produces duplicates, the form field will show duplicate options
    favorite_article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(category__name='Science')
    )

    class Meta:
        app_label = 'test_app'

# Create tables
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Category)
    schema_editor.create_model(Article)
    schema_editor.create_model(Author)

# Create test data
# Create a category
science_cat = Category.objects.create(name='Science')
arts_cat = Category.objects.create(name='Arts')

# Create articles
article1 = Article.objects.create(title='Article 1', category=science_cat)
article2 = Article.objects.create(title='Article 2', category=science_cat)
article3 = Article.objects.create(title='Article 3', category=arts_cat)

# Create an author form
class AuthorForm(ModelForm):
    class Meta:
        model = Author
        fields = ['name', 'favorite_article']

form = AuthorForm()

# Get the choices for the favorite_article field
choices = list(form.fields['favorite_article'].queryset.values_list('pk', flat=True))

# The limit_choices_to should filter articles to only those in 'Science' category
# There are 2 such articles: article1 and article2
# If the bug exists, there might be duplicates in the queryset due to the join
# causing the same article to appear multiple times.

# Check for duplicates
assert len(choices) == len(set(choices)), f"Duplicate options found in formfield choices: {choices}"

# Also verify that only correct articles are included
expected_pks = {article1.pk, article2.pk}
actual_pks = set(choices)
assert actual_pks == expected_pks, f"Expected choices {expected_pks}, got {actual_pks}"

print("Test passed: No duplicate options in formfield.")
sys.exit(0)
