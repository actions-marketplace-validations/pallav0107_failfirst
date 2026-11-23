import os
import sys

# Configure Django settings before importing django.db.models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
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
    )
    django.setup()

from django.db import models

# Reproduce the issue exactly as described
f = models.CharField(max_length=200)
d = {f: 1}

class Book(models.Model):
    title = f

# The assertion fails if __hash__ changes after assignment to the model class
# If the bug is fixed, f should still be in d
assert f in d, "Field instance was lost from dict after being assigned to a model class"

sys.exit(0)
