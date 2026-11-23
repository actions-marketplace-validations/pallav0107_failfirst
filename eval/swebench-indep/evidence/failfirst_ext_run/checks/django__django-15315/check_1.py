import os
import sys

# Configure Django settings before importing django modules
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

# The assertion should pass if the bug is fixed (hash is immutable)
# If the hash changed after assigning to the model class, 'f in d' will be False
# because dicts rely on stable hashes for lookup.
assert f in d, "Field hash changed after being assigned to a model class, breaking dict lookup."

sys.exit(0)
