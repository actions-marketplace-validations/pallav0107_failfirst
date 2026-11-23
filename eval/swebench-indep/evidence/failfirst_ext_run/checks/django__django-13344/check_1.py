import os
import sys
import asyncio

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-only',
        ROOT_URLCONF='',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        MIDDLEWARE=[
            'check.TestMiddleware',  # This will be defined below or we use a dynamic approach
        ],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        USE_TZ=True,
    )

django.setup()

# Now we can import Django components
from django.http import HttpResponse
from django.core.handlers.asgi import ASGIHandler
from django.utils.decorators import sync_to_async

# We need to simulate the middleware chain behavior described in the issue.
# The issue states that the FIRST middleware receives a coroutine instead of an HttpResponse
# in ASGI mode.

# Let's create a simple test to verify if get_response returns a coroutine or an HttpResponse
# when called within the ASGI handler context.

# However, directly testing the internal middleware chain execution is complex.
# A more direct way is to look at how ASGIHandler handles the response.
# In Django 3.2+, the ASGIHandler should await the inner handler and ensure
# that process_response receives an HttpResponse, not a coroutine.

# Let's try to reproduce the exact scenario:
# 1. Create an ASGI application.
# 2. Send a request.
# 3. Check what the first middleware's process_response receives.

# Since we cannot easily inject a custom middleware into the running Django app 
# without modifying settings which are already configured, we will manually 
# construct the middleware chain logic similar to how Django does it.

# Actually, the best way is to use Django's test client or ASGI test utilities if available,
# but the issue is specific to the internal passing of coroutines.

# Let's look at the source of the bug. The bug was in `django.core.handlers.asgi.ASGIHandler`.
# Specifically, in how it calls `get_response` and then passes the result to `process_response`.

# We will write a script that mimics the ASGI handler's behavior for a single middleware
# and checks if the response passed to process_response is an HttpResponse.

from django.core.handlers.base import BaseHandler
from django.http import HttpRequest, HttpResponse
from asgiref.sync import sync_to_async
import inspect

class TestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.received_response_type = None

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_response(self, request, response):
        self.received_response_type = type(response)
        return response

# To test this properly, we need to run the actual ASGI handler code path.
# Let's import the ASGIHandler and see if we can trigger the bug.

from django.core.handlers.asgi import ASGIHandler

# We need a minimal view
def dummy_view(request):
    return HttpResponse("Hello World")

# We need to wrap this view in a URL resolver or just call the handler directly?
# ASGIHandler expects a scope, receive, send.

# Let's try a different approach: Inspect the code or use a unit-test-like setup.
# The issue is that `get_response` returns a coroutine in async mode, but 
# `process_response` is synchronous (usually). If the middleware is wrapped with 
# MiddlewareMixin, it might handle it, but the raw call might pass a coroutine.

# Let's look at how Django 3.2 fixed this.
# The fix likely involves awaiting the response before passing it to process_response.

# We will create a minimal ASGI test.
import asyncio
from unittest.mock import MagicMock

async def test_asgi_middleware_response():
    """
    This test simulates the ASGI request handling and checks if the first 
    middleware's process_response receives an HttpResponse or a coroutine.
    """
    
    # Capture the type of response received by the first middleware
    received_type = None
    
    class CapturingMiddleware:
        def __init__(self, get_response):
            self.get_response = get_response

        async def __call__(self, request):
            # In async mode, get_response might be a coroutine or async function
            response = await self.get_response(request)
            return response
        
        def process_response(self, request, response):
            nonlocal received_type
            received_type = type(response)
            return response

    # We need to patch the middleware list in ASGIHandler or create a custom handler
    # This is getting complicated. Let's try to use Django's built-in test tools for ASGI.
    
    from django.test import AsyncClient
    
    # Configure URLs
    from django.urls import path
    from django.http import HttpResponse
    
    def my_view(request):
        return HttpResponse("OK")
        
    urlpatterns = [
        path('', my_view),
    ]
    
    # Re-configure settings with our middleware and urls
    from django.conf import settings
    from django.urls import clear_url_caches, set_urlconf
    import importlib
    
    # We need to reload settings to apply new MIDDLEWARE and ROOT_URLCONF
    # But settings are already configured. We can override them.
    
    settings.ROOT_URLCONF = __name__ # Use current module for urls? No, we defined urlpatterns locally.
    
    # Let's define a proper urlconf module dynamically
    import types
    urlconf_module = types.ModuleType('urlconf')
    urlconf_module.urlpatterns = [
        path('', my_view),
    ]
    sys.modules['test_urlconf'] = urlconf_module
    settings.ROOT_URLCONF = 'test_urlconf'
    
    # Clear URL cache
    clear_url_caches()
    set_urlconf(importlib.import_module(settings.ROOT_URLCONF))
    
    # Define the middleware in a way Django can find it
    # We'll put CapturingMiddleware in a module that Django can import
    import check as check_module
    check_module.CapturingMiddleware = CapturingMiddleware
    
    settings.MIDDLEWARE = [
        'check.CapturingMiddleware',
        'django.middleware.common.CommonMiddleware',
    ]
    
    # Reload middleware handling
    # This is tricky because Django loads middleware at startup.
    # We might need to create a new ASGIHandler instance.
    
    handler = ASGIHandler()
    
    # Create a mock scope
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/',
        'query_string': b'',
        'headers': [],
    }
    
    # Mock receive and send
    async def receive():
        return {'type': 'http.request', 'body': b''}
        
    sent_messages = []
    async def send(message):
        sent_messages.append(message)
        
    # Call the handler
    await handler(scope, receive, send)
    
    # Check if we captured the type
    # Note: The CapturingMiddleware.process_response is synchronous.
    # If the bug exists, 'response' passed to it might be a coroutine.
    
    if received_type is None:
        # Middleware might not have been called correctly in this manual setup
        # Let's rely on the fact that if the bug is present, an error might occur 
        # or the type is wrong.
        
        # Alternative: Check the source code or use a more robust integration test.
        # Given the constraints, let's assume the AsyncClient approach is better.
        pass
        
    return received_type

# The above manual approach is fragile. Let's use Django's AsyncTestClient if available 
# or just standard AsyncClient from django.test.

from django.test import AsyncClient, override_settings

@override_settings(
    ROOT_URLCONF='test_urlconf',
    MIDDLEWARE=[
        'check.CapturingMiddlewareForTest',
        'django.middleware.common.CommonMiddleware',
    ]
)
async def run_test():
    # We need to define CapturingMiddlewareForTest globally so it can be imported by string
    pass

# Let's simplify. We will define a middleware that records the type.
# And use AsyncClient to make a request.

# Define the middleware class globally
class CapturingMiddlewareForTest:
    def __init__(self, get_response):
        self.get_response = get_response
        self.response_type_in_process_response = None

    async def __call__(self, request):
        response = await self.get_response(request)
        return response

    def process_response(self, request, response):
        self.response_type_in_process_response = type(response)
        return response

# Add it to the current module so 'check.CapturingMiddlewareForTest' works
sys.modules[__name__].CapturingMiddlewareForTest = CapturingMiddlewareForTest

# Define URLconf
import types
urlconf = types.ModuleType('test_urlconf_final')
def final_view(request):
    return HttpResponse("Final OK")
urlconf.urlpatterns = [path('', final_view)]
sys.modules['test_urlconf_final'] = urlconf

async def main():
    from django.test import AsyncClient
    from django.conf import settings
    
    # Update settings
    settings.ROOT_URLCONF = 'test_urlconf_final'
    settings.MIDDLEWARE = [
        'check.CapturingMiddlewareForTest',
        'django.middleware.common.CommonMiddleware',
    ]
    
    # We need to force Django to reload its middleware stack.
    # Creating a new ASGIHandler should do this.
    from django.core.handlers.asgi import ASGIHandler
    handler = ASGIHandler()
    
    # Patch the handler's load_middleware to ensure it picks up new settings?
    # Actually, ASGIHandler.load_middleware is called in __init__.
    
    client = AsyncClient()
    
    # Make a request
    response = await client.get('/')
    
    # Find the middleware instance
    # The middleware instances are stored in handler._middleware_chain or similar?
    # It's hard to access the specific instance.
    
    # Alternative: Check the response content to ensure it worked, 
    # and rely on a side-effect.
    
    # Let's modify the middleware to store the type in a global variable
    global last_received_type
    last_received_type = None
    
    class GlobalCapturingMiddleware:
        def __init__(self, get_response):
            self.get_response = get_response

        async def __call__(self, request):
            response = await self.get_response(request)
            return response

        def process_response(self, request, response):
            global last_received_type
            last_received_type = type(response)
            return response
            
    sys.modules[__name__].GlobalCapturingMiddleware = GlobalCapturingMiddleware
    
    settings.MIDDLEWARE = [
        'check.GlobalCapturingMiddleware',
        'django.middleware.common.CommonMiddleware',
    ]
    
    # Create new handler to reload middleware
    new_handler = ASGIHandler()
    
    # We can't easily inject this handler into the AsyncClient.
    # AsyncClient creates its own handler.
    
    # Let's look at how AsyncClient works. It uses ClientHandler which is WSGI/ASGI agnostic?
    # No, AsyncClient uses ASGIHandler.
    
    # The problem is that Django caches the handler.
    
    # Let's try a different tactic: Directly test the ASGIHandler's behavior 
    # by calling it with a mock scope, as attempted before, but ensuring 
    # the middleware is correctly loaded.
    
    # Reset URL conf
    clear_url_caches()
    set_urlconf(importlib.import_module('test_urlconf_final'))
    
    # Create scope
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/',
        'query_string': b'',
        'headers': [],
        'server': ('127.0.0.1', 8000),
        'scheme': 'http',
    }
    
    async def receive():
        return {'type': 'http.request', 'body': b''}
        
    sent = []
    async def send(msg):
        sent.append(msg)
        
    # Instantiate handler with current settings
    handler = ASGIHandler()
    
    await handler(scope, receive, send)
    
    # Check global variable
    assert last_received_type is not None, "Middleware process_response was not called"
    
    # The bug is if last_received_type is coroutine
    # Correct behavior: it should be HttpResponse or a subclass
    
    if inspect.isclass(last_received_type) and issubclass(last_received_type, HttpResponse):
        # Correct
        return 0
    elif inspect.iscoroutinefunction(last_received_type) or (hasattr(last_received_type, '__await__')):
         # This check is wrong, last_received_type is a TYPE, not an instance.
         # We stored type(response).
         # If response was a coroutine, type(response) would be <class 'coroutine'>
         pass
         
    # Check if the type is 'coroutine'
    if last_received_type.__name__ == 'coroutine':
        # Bug present
        raise AssertionError(f"Bug present: process_response received a coroutine instead of HttpResponse. Type: {last_received_type}")
    else:
        # Bug fixed
        return 0

# Run the async test
try:
    result = asyncio.run(main())
    sys.exit(0)
except AssertionError as e:
    print(e)
    sys.exit(1)
except Exception as e:
    print(f"Error during test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
