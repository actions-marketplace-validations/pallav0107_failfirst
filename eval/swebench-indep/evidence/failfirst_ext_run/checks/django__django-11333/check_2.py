import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={},
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        ROOT_URLCONF='test_urls',
        SECRET_KEY='test-secret-key',
    )

django.setup()

# Create a minimal URL configuration module in memory
import types
test_urls_module = types.ModuleType('test_urls')
exec("""
from django.urls import path

def dummy_view(request):
    return None

urlpatterns = [
    path('test/', dummy_view, name='test-name'),
]
""", test_urls_module.__dict__)
sys.modules['test_urls'] = test_urls_module

# Import the relevant functions
from django.urls.resolvers import get_resolver
from django.urls.base import get_urlconf, set_urlconf

def main():
    # Ensure we start with a clean state regarding urlconf
    # In a fresh process, get_urlconf() returns None until set_urlconf is called.
    
    # 1. Call get_resolver BEFORE set_urlconf is called.
    # This simulates calling reverse() or similar at import time.
    # get_urlconf() should be None here.
    initial_urlconf = get_urlconf()
    assert initial_urlconf is None, f"Expected initial urlconf to be None, got {initial_urlconf}"
    
    resolver_before = get_resolver(initial_urlconf)
    
    # 2. Simulate request handling which calls set_urlconf(settings.ROOT_URLCONF)
    root_urlconf = settings.ROOT_URLCONF
    set_urlconf(root_urlconf)
    
    # 3. Call get_resolver AFTER set_urlconf is called.
    # get_urlconf() should now be settings.ROOT_URLCONF
    current_urlconf = get_urlconf()
    assert current_urlconf == root_urlconf, f"Expected urlconf to be {root_urlconf}, got {current_urlconf}"
    
    resolver_after = get_resolver(current_urlconf)
    
    # The issue states that multiple URLResolvers may be constructed because
    # get_resolver is cached based on its argument. 
    # Before the fix: resolver_before (cached with key None) != resolver_after (cached with key 'test_urls')
    # After the fix: get_resolver should normalize the input so that both calls return the same instance.
    
    # Check if they are the same object
    if resolver_before is not resolver_after:
        print(f"FAIL: Two different URLResolver instances were created.")
        print(f"  Resolver before (key=None): {id(resolver_before)}")
        print(f"  Resolver after (key={root_urlconf}): {id(resolver_after)}")
        sys.exit(1)
    else:
        print("PASS: Same URLResolver instance returned.")
        sys.exit(0)

if __name__ == '__main__':
    main()
