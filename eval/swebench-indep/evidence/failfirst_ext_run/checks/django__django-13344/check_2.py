import os
import sys
import asyncio

# Configure Django settings before importing anything else from Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-only',
        ROOT_URLCONF='',
        MIDDLEWARE=[
            'check.TestMiddleware',
            'django.middleware.common.CommonMiddleware',
        ],
        INSTALLED_APPS=[],
        DATABASES={},
        USE_TZ=True,
    )

django.setup()

from django.http import HttpResponse
from django.core.handlers.asgi import ASGIHandler
from django.utils.deprecation import MiddlewareMixin

# Global variable to capture the response type seen by the first middleware
captured_response_type = None

class TestMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        global captured_response_type
        captured_response_type = type(response)
        return response

def get_simple_view(request):
    return HttpResponse("OK")

async def run_check():
    global captured_response_type
    
    # Create an ASGI handler with a simple view
    handler = ASGIHandler(get_simple_view)
    
    # Construct a minimal ASGI scope for a GET request
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/',
        'query_string': b'',
        'headers': [],
        'server': ('127.0.0.1', 8000),
    }
    
    # Mock receive and send callables
    async def receive():
        return {'type': 'http.request', 'body': b''}
    
    sent_messages = []
    async def send(message):
        sent_messages.append(message)
    
    # Run the ASGI application
    await handler(scope, receive, send)
    
    # Check if the response passed to the first middleware was a coroutine
    # If it was a coroutine, the issue is present (wrong behavior).
    # If it was an HttpResponse, the issue is fixed (correct behavior).
    
    assert captured_response_type is not None, "Middleware was not called"
    
    # The issue states that the first middleware receives a coroutine instead of HttpResponse.
    # Correct behavior: It should receive an HttpResponse.
    # Wrong behavior: It receives a coroutine object.
    
    import inspect
    if inspect.iscoroutine(captured_response_type) or captured_response_type == type(asyncio.sleep(0)):
        # This branch handles if captured_response_type IS a coroutine instance (which shouldn't happen for type(), 
        # but let's be safe about what we captured). Actually, type() returns the class.
        # So if response was a coroutine, type(response) would be <class 'coroutine'>.
        raise AssertionError(f"First middleware received a coroutine instead of HttpResponse. Type: {captured_response_type}")
    
    assert captured_response_type == HttpResponse, f"Expected HttpResponse, got {captured_response_type}"

if __name__ == '__main__':
    try:
        asyncio.run(run_check())
        sys.exit(0)
    except AssertionError as e:
        print(f"Assertion failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during check: {e}", file=sys.stderr)
        sys.exit(1)
