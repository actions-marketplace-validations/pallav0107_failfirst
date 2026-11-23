import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-script-only',
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
        ROOT_URLCONF='',
    )

django.setup()

from django.core.management.commands.runserver import Command as RunserverCommand
from django.utils.ipv6 import is_valid_ipv6_address

def check_runserver_address_format():
    """
    Check if the runserver command correctly formats the address '0' 
    to '0.0.0.0' in the startup message.
    
    The issue states that `runserver 0:8000` outputs "Starting development server at http://0:8000/"
    but it should output "Starting development server at http://0.0.0.0:8000/".
    """
    
    # Create an instance of the runserver command
    cmd = RunserverCommand()
    
    # We need to check how the address is handled when '0' is provided.
    # The core logic for determining the display address is in the get_handler method 
    # or related setup methods, but specifically the message is printed in inner_run.
    # However, we can inspect the normalization logic directly.
    
    # In Django's runserver, the address '0' is a shorthand for '0.0.0.0'.
    # Let's look at how the command parses and normalizes the address.
    
    # The relevant code usually resides in django.core.management.commands.runserver
    # Specifically, there is often a helper function or method that resolves '0' to '0.0.0.0'.
    
    # Let's simulate what happens when addrport is '0:8000'
    addrport = '0:8000'
    
    # Parse the addrport
    if ':' in addrport:
        host, port = addrport.rsplit(':', 1)
    else:
        host = ''
        port = addrport
        
    # Normalize host
    # According to Django source (historically), if host is '0', it should be treated as '0.0.0.0'
    # for binding purposes, and importantly for the display message.
    
    # Let's check the actual behavior by looking at the normalize_addr_port or similar logic
    # In recent Django versions, this logic might be in django.core.servers.basehttp or similar.
    
    # Actually, let's look at the `get_default_address` or how the command handles the argument.
    # The command class has a `handle` method which calls `run`.
    
    # A more direct way: Check if the string representation used in the log message is correct.
    # The message is constructed like: f"Starting development server at http://{addr}:{port}/"
    
    # We need to find where '0' gets converted.
    # In django/core/management/commands/runserver.py:
    # def handle(self, *args, **options):
    #     ...
    #     self.addr = options['addr']
    #     self.port = options['port']
    #     ...
    
    # The parsing happens in the argument parser or early in handle.
    # If we pass '0:8000', args[0] is '0:8000'.
    
    # Let's use the internal utility if available, or replicate the logic.
    # Django uses django.core.servers.basehttp.WSGIServer which binds to the address.
    
    # Key insight: The issue is about the *display* string.
    # If the user provides '0', the server binds to '0.0.0.0' (all interfaces).
    # The display should reflect the canonical form '0.0.0.0' so the URL is clickable/valid.
    
    # Let's import the specific function that normalizes the address if it exists,
    # or check the Command's behavior.
    
    try:
        from django.core.management.commands.runserver import Command
        cmd = Command()
        
        # Mock the options as if parsed from '0:8000'
        # The parser splits addrport into addr and port.
        # For '0:8000', addr='0', port='8000'.
        
        # We need to see what the command does with addr='0'.
        # In Django 4.2, there is a method `get_handler` but the address normalization
        # for display might happen in `inner_run` or when constructing the url.
        
        # Let's look at the source code logic conceptually:
        # If addr == '0', it should be displayed as '0.0.0.0'.
        
        # We can test this by checking if there is a normalization step.
        # In django/utils/ipv6.py or similar, there might be helpers.
        
        # Actually, the most reliable way without running the server is to check
        # if the Command class or its dependencies normalize '0' to '0.0.0.0' for display.
        
        # Let's try to instantiate and see if we can access the normalized address.
        # Since we can't easily run the server, we'll check the logic used to generate the message.
        
        # In Django 4.2, the runserver command uses:
        # from django.core.servers.basehttp import WSGIServer
        # The address passed to WSGIServer is used for binding.
        
        # However, the print statement is in the command itself.
        # Let's check if the command normalizes the address before printing.
        
        # Looking at Django 4.2 source code for runserver:
        # In handle(), it calls self.run(**options)
        # In run(), it calls self.inner_run(addr, port, ...)
        # In inner_run(), it prints:
        # self.stdout.write(f"Starting development server at http://{addr}:{port}/")
        
        # So the question is: what is `addr` at that point?
        # The `addr` comes from options['addr'].
        # How is options['addr'] set?
        # In handle(), if args are provided, it parses them.
        # parse_addr_port(addrport) returns (addr, port).
        
        # Let's find parse_addr_port. It's likely in the same file or utils.
        from django.core.management.commands.runserver import parse_addr_port
        
        addr, port = parse_addr_port('0:8000')
        
        # If parse_addr_port returns ('0', '8000'), then the message will be http://0:8000/
        # If it returns ('0.0.0.0', '8000'), then the message will be http://0.0.0.0:8000/
        
        # According to the issue, it currently returns '0', which is wrong.
        # The fix should make it return '0.0.0.0'.
        
        assert addr == '0.0.0.0', f"Expected address to be normalized to '0.0.0.0', but got '{addr}'. The issue is NOT fixed."
        
        # If we reach here, the address is correctly normalized.
        print("Check passed: Address '0' is correctly normalized to '0.0.0.0'.")
        sys.exit(0)
        
    except ImportError as e:
        # Fallback if parse_addr_port is not directly importable or changed location
        # We can try to simulate the parsing logic found in Django sources
        
        # Typical logic in Django < some version or if helper moved:
        def manual_parse_addr_port(addrport):
            """Mimic Django's parsing logic."""
            if addrport.startswith('['):
                # IPv6
                idx = addrport.find(']')
                if idx == -1:
                    raise ValueError("Invalid IPv6 address")
                addr = addrport[1:idx]
                remaining = addrport[idx+1:]
                if remaining.startswith(':'):
                    port = remaining[1:]
                else:
                    port = ''
            else:
                if ':' in addrport:
                    addr, port = addrport.rsplit(':', 1)
                else:
                    addr = ''
                    port = addrport
            
            # Normalization logic that SHOULD exist for the bug to be fixed
            if addr == '0':
                addr = '0.0.0.0'
                
            return addr, port

        # This manual check doesn't help us verify the *actual* Django code.
        # We must rely on the imported function. If import failed, something is wrong with our approach.
        # Let's try another import path just in case.
        
        # In Django 4.2, parse_addr_port is defined in django.core.management.commands.runserver
        raise AssertionError(f"Could not import necessary Django internals to verify the fix: {e}")

if __name__ == '__main__':
    check_runserver_address_format()
