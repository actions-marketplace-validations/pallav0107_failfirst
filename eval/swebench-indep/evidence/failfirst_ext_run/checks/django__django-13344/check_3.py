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
        SECRET_KEY='test-secret-key-for-check-script',
        ROOT_URLCONF='',
        MIDDLEWARE=[
            'django.middleware.security.SecurityMiddleware',
        ],
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
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

from django.core.handlers.asgi import ASGIHandler
from django.http import HttpRequest, HttpResponse
from django.utils.decorators import sync_and_async_middleware


def test_asgi_middleware_response_type():
    """
    Test that the first middleware in the chain receives an HttpResponse object,
    not a coroutine, in its process_response method when running under ASGI.
    
    This reproduces the issue where the first middleware received a coroutine
    instead of an HttpResponse.
    """
    
    # Track what the first middleware receives
    received_response_type = None
    
    class TrackingMiddleware:
        def __init__(self, get_response):
            self.get_response = get_response
        
        async def __call__(self, request):
            response = await self.get_response(request)
            return response
            
        def process_response(self, request, response):
            nonlocal received_response_type
            received_response_type = type(response)
            return response

    # Create a simple view
    async def simple_view(request):
        return HttpResponse("Hello World")

    # Build the handler with our tracking middleware as the first one
    # We need to simulate the middleware chain construction
    
    from django.core.handlers.base import BaseHandler
    
    # Create a minimal ASGI handler
    handler = ASGIHandler()
    
    # Manually construct a middleware chain to test the behavior
    # The issue is about how ASGIHandler calls middleware
    
    # Let's directly test the internal behavior by examining how 
    # ASGIHandler._get_response_async works
    
    import inspect
    
    # Check the source or behavior of ASGIHandler
    # In Django 3.2+, the fix should ensure that response is awaited 
    # before being passed to middleware's process_response
    
    # Let's create a more direct test
    
    async def run_test():
        nonlocal received_response_type
        
        # Create a mock request
        scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/',
            'query_string': b'',
            'headers': [],
        }
        
        # We'll patch the middleware processing to capture what's passed
        original_process_response = None
        
        class CaptureMiddleware:
            def __init__(self, get_response):
                self.get_response = get_response
            
            async def __call__(self, request):
                response = await self.get_response(request)
                # This is where process_response would be called in sync middleware
                # For MiddlewareMixin, process_response is called after get_response
                if hasattr(self, 'process_response'):
                    response = self.process_response(request, response)
                return response
                
            def process_response(self, request, response):
                nonlocal received_response_type
                received_response_type = type(response)
                return response
        
        # Create a simple async view
        async def test_view(request):
            return HttpResponse("Test response")
        
        # Simulate the middleware chain
        # In Django's ASGI handler, middlewares are wrapped around the view
        
        # Let's trace through what happens:
        # 1. ASGIHandler creates the request
        # 2. It calls the middleware chain
        # 3. Each middleware calls get_response which eventually returns a response
        
        # The bug was that for the FIRST middleware, the response returned by 
        # get_response was a coroutine instead of an awaited HttpResponse
        
        # Let's check if we can reproduce this by looking at how 
        # django.utils.deprecation.MiddlewareMixin handles async
        
        from django.utils.deprecation import MiddlewareMixin
        
        class TestMiddleware(MiddlewareMixin):
            def process_response(self, request, response):
                nonlocal received_response_type
                received_response_type = type(response)
                return response
        
        # Create the handler chain manually
        def get_response_simple(request):
            return test_view(request)
        
        # Wrap with middleware
        middleware_instance = TestMiddleware(get_response_simple)
        
        # Create a mock request object
        from django.core.handlers.asgi import ASGIRequest
        from asgiref.sync import sync_to_async
        
        # Create a proper ASGI request
        class MockReceive:
            async def __call__(self):
                return {'type': 'http.request', 'body': b''}
        
        class MockSend:
            async def __call__(self, message):
                pass
        
        mock_receive = MockReceive()
        mock_send = MockSend()
        
        # Create ASGIRequest
        request = ASGIRequest(scope, mock_receive)
        
        # Call the middleware - this should trigger process_response
        # For MiddlewareMixin with async, it should handle awaiting properly
        
        try:
            result = await middleware_instance(request)
        except Exception as e:
            # If there's an error, we might not get to process_response
            pass
        
        # Check what type was received
        if received_response_type is None:
            # process_response wasn't called, try another approach
            raise AssertionError("process_response was not called")
        
        # The fix ensures that response is an HttpResponse, not a coroutine
        import types
        if received_response_type == types.CoroutineType:
            raise AssertionError(f"First middleware received coroutine instead of HttpResponse. Got: {received_response_type}")
        
        assert received_response_type == HttpResponse, f"Expected HttpResponse, got {received_response_type}"
    
    # Run the async test
    asyncio.run(run_test())


if __name__ == '__main__':
    try:
        test_asgi_middleware_response_type()
        print("PASS: First middleware correctly receives HttpResponse, not coroutine")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
