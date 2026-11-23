import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django.conf as conf

if not conf.settings.configured:
    conf.settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-only',
        ROOT_URLCONF='',  # Start with empty URLconf to simulate the issue state
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )

django.setup()

from django.urls import reverse, get_resolver, set_urlconf
from django.urls.resolvers import URLResolver
import functools

# We need to check if get_resolver creates multiple instances when called
# with None (before set_urlconf) and then with the actual ROOT_URLCONF (after set_urlconf).

# To make this test meaningful, we need a real URLconf.
# Let's create a simple one in memory or use a standard one.
# Since we can't create files, we'll define a simple URL pattern list and assign it.

from django.urls import path

def dummy_view(request):
    return None

urlpatterns = [
    path('test/', dummy_view, name='test-view'),
]

# Step 1: Clear any existing cache in get_resolver to ensure a clean state.
# get_resolver is decorated with lru_cache. We need to clear it.
get_resolver.cache_clear()

# Step 2: Simulate the state before request handling.
# Typically, get_urlconf() returns None initially if set_urlconf hasn't been called.
# However, get_resolver uses get_urlconf() internally.
# Let's verify what get_urlconf returns initially.
from django.urls.base import get_urlconf

initial_urlconf = get_urlconf()
# In a fresh setup without middleware running, this might be None or the setting.
# The issue states: "Initially it will be called with None".
# Let's force the state to match the issue description by ensuring get_urlconf returns None.
# Actually, set_urlconf(None) sets it to None.
set_urlconf(None)

assert get_urlconf() is None, "Precondition failed: get_urlconf should be None"

# Step 3: Call get_resolver while urlconf is None.
# This should create a resolver for None.
resolver_1 = get_resolver(None) # Explicitly pass None to match the internal call when get_urlconf() is None
# Note: The issue says reverse calls get_resolver with result of get_urlconf.
# So if get_urlconf() is None, it calls get_resolver(None).

# Step 4: Now simulate request handling which calls set_urlconf(settings.ROOT_URLCONF).
# But first, we need a valid ROOT_URLCONF module. 
# Since we configured ROOT_URLCONF='' above, that's invalid. 
# Let's change settings.ROOT_URLCONF to point to a module we can control or just use a dummy module approach.
# Actually, we can just set the urlconf to our urlpatterns directly? No, set_urlconf expects a string (module path).
# Let's create a temporary module in sys.modules.

import types
dummy_module = types.ModuleType('dummy_urls')
dummy_module.urlpatterns = urlpatterns
sys.modules['dummy_urls'] = dummy_module

# Update settings to use this dummy module
conf.settings.ROOT_URLCONF = 'dummy_urls'

# Now call set_urlconf as BaseHandler.get_response would
set_urlconf(conf.settings.ROOT_URLCONF)

assert get_urlconf() == 'dummy_urls', "Postcondition failed: get_urlconf should be 'dummy_urls'"

# Step 5: Call get_resolver again.
# Internally, reverse/get_resolver will now call get_resolver('dummy_urls').
resolver_2 = get_resolver('dummy_urls')

# Step 6: Check if resolver_1 and resolver_2 are the same object.
# If the bug exists, they are different objects because the cache key was different (None vs 'dummy_urls').
# If the fix is applied, get_resolver should look up settings.ROOT_URLCONF when the argument is None/default,
# or the caching strategy has changed to avoid this duplication.

# Wait, let's look at the proposed fix: "modify get_resolver to look up settings.ROOT_URLCONF before the memoized function call."
# This implies that if get_resolver is called with None (or default), it should substitute settings.ROOT_URLCONF BEFORE caching/lookup.
# So, get_resolver(None) should effectively become get_resolver(settings.ROOT_URLCONF).

# Let's re-run the scenario carefully.
get_resolver.cache_clear()

# State 1: urlconf is None
set_urlconf(None)
# When get_resolver is called without arguments, it defaults to get_urlconf().
# def get_resolver(urlconf=None):
#     if urlconf is None:
#         urlconf = get_urlconf()
#     ...
# So get_resolver() -> get_resolver(None).

# If the fix is in place:
# def get_resolver(urlconf=None):
#     if urlconf is None:
#         urlconf = get_urlconf() or settings.ROOT_URLCONF  <-- Hypothetical fix
#     
# Let's check the current behavior.

# Call 1: Before set_urlconf to ROOT_URLCONF
set_urlconf(None)
r1 = get_resolver() # Internally resolves to get_resolver(None)

# Call 2: After set_urlconf to ROOT_URLCONF
set_urlconf('dummy_urls')
r2 = get_resolver() # Internally resolves to get_resolver('dummy_urls')

# If the bug is present, r1 and r2 are different instances because cached separately.
# If the bug is fixed, r1 should have used 'dummy_urls' (from settings) even when get_urlconf() was None?
# Or rather, the fix ensures that we don't create a resolver for None if we know the ROOT_URLCONF.

# Let's read the issue again: "My proposed solution is just to modify get_resolver to look up settings.ROOT_URLCONF before the memoized function call."
# This suggests that if the passed urlconf is None (or resulting from get_urlconf being None), it should fallback to settings.ROOT_URLCONF.

# So, if fixed:
# 1. set_urlconf(None). get_resolver() -> gets None from get_urlconf. Checks settings.ROOT_URLCONF ('dummy_urls'). Uses 'dummy_urls'. Caches/returns Resolver('dummy_urls').
# 2. set_urlconf('dummy_urls'). get_resolver() -> gets 'dummy_urls' from get_urlconf. Uses 'dummy_urls'. Hits cache. Returns same Resolver('dummy_urls').

# If NOT fixed:
# 1. set_urlconf(None). get_resolver() -> gets None. Caches/returns Resolver(None).
# 2. set_urlconf('dummy_urls'). get_resolver() -> gets 'dummy_urls'. Caches/returns Resolver('dummy_urls').
# r1 != r2.

# Therefore, the check is: are r1 and r2 the same object?

if r1 is r2:
    # Behavior is correct (fixed)
    sys.exit(0)
else:
    # Behavior is wrong (bug present)
    raise AssertionError(f"Multiple URLResolvers constructed: {id(r1)} != {id(r2)}. The optimization is missing.")
