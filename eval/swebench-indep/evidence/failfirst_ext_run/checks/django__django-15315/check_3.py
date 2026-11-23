import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

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
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

from django.db import models

# Reproduce the issue exactly as described
f = models.CharField(max_length=200)
d = {f: 1}

class Book(models.Model):
    title = f
    
    class Meta:
        app_label = 'test_app'

# The assertion that should pass if the bug is fixed (hash is immutable)
# If __hash__ changes after assignment to the model class, f will not be found in d
assert f in d, "Field hash changed after being assigned to a model class, breaking dict lookup"

sys.exit(0)
