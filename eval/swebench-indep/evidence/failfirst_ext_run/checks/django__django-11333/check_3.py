import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key',
        ROOT_URLCONF='django.urls',  # Use a simple existing urlconf or define one
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )

django.setup()

# Define a simple URLconf for testing
from django.urls import path, include

def dummy_view(request):
    return None

urlpatterns = [
    path('test/', dummy_view, name='test-view'),
]

# We need to make sure this urlpatterns is used. 
# Let's create a temporary module for it.
import types
urlconf_module = types.ModuleType('test_urlconf')
urlconf_module.urlpatterns = urlpatterns
sys.modules['test_urlconf'] = urlconf_module

# Update settings to use our test urlconf
settings.ROOT_URLCONF = 'test_urlconf'

# Now let's reproduce the issue.
# The issue states that get_resolver is called with different arguments (None vs settings.ROOT_URLCONF)
# leading to multiple URLResolver instances.

from django.urls.resolvers import get_resolver, set_urlconf
from django.urls import reverse

# Clear any existing cache to start fresh
get_resolver.cache_clear()

# 1. Call get_resolver BEFORE set_urlconf is implicitly called by request handling.
# In a typical scenario, this might happen at import time or during early initialization.
# At this point, get_urlconf() returns None because set_urlconf hasn't been called yet.
resolver_before = get_resolver()

# Check how many resolvers are in the cache now.
# If the bug exists, calling get_resolver() with None creates one entry.
cache_info_before = get_resolver.cache_info()
assert cache_info_before.currsize >= 1, "Expected at least one resolver in cache after first call"

# 2. Simulate what happens when a request is handled: set_urlconf is called.
# BaseHandler.get_response calls set_urlconf(settings.ROOT_URLCONF)
set_urlconf(settings.ROOT_URLCONF)

# 3. Call get_resolver AFTER set_urlconf.
# Now get_urlconf() returns settings.ROOT_URLCONF ('test_urlconf').
# If the bug exists, this will create a NEW URLResolver instance because the argument is different.
resolver_after = get_resolver()

# Check if they are the same object.
# If fixed, they should be the same instance (or the cache should have been managed to avoid duplication).
# The issue proposes modifying get_resolver to look up settings.ROOT_URLCONF before memoization.
# This means both calls should effectively use the same key (the actual urlconf string), 
# so they should return the same resolver instance.

# Let's check the identity.
if resolver_before is not resolver_after:
    # This indicates the bug is present: two different resolvers were created.
    print("BUG DETECTED: Two different URLResolver instances were created.")
    print(f"Resolver before: {id(resolver_before)}")
    print(f"Resolver after: {id(resolver_after)}")
    sys.exit(1)
else:
    # The fix is working: only one resolver instance exists.
    print("FIX VERIFIED: Same URLResolver instance returned.")
    sys.exit(0)
