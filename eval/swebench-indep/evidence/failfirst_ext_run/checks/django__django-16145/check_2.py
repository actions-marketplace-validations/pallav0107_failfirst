import os
import sys

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key-for-check-only',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        ROOT_URLCONF='',
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        USE_TZ=True,
    )

django.setup()

from django.core.management.commands.runserver import Command as RunserverCommand
from django.core.management.base import CommandParser

def get_server_address_output(addr):
    """
    Simulates the logic in runserver that determines the displayed URL.
    We inspect the handle method or the underlying server creation to see
    what address is reported.
    
    The issue is about the string printed: "Starting development server at http://0:8000/"
    vs "http://0.0.0.0:8000/".
    
    In Django's runserver, the address parsing happens in `run` method of BaseRunserverCommand.
    Specifically, it uses `self.addr` and `self.port`.
    
    Let's look at how the address is normalized.
    """
    cmd = RunserverCommand()
    # Create a parser to parse the argument '0:8000'
    parser = CommandParser(prog='manage.py')
    cmd.add_arguments(parser)
    
    # Parse arguments
    args = parser.parse_args(['0:8000'])
    
    # The command stores these in self.addr and self.port after validate
    # We need to mimic the setup done in handle() or run()
    
    # In Django 4.2, the logic is roughly:
    # addr, port = args.addrport.split(':') if ':' in args.addrport else (args.addrport, '8000')
    # But actually, it's handled by `parse_addr_port` utility or similar.
    
    # Let's look at django.core.management.commands.runserver.Command.handle
    # It calls self.run(**options)
    # Inside run, it does:
    # addr, port = self.addr, self.port
    # ...
    # url = f"http://{addr}:{port}/"
    
    # How are self.addr and self.port set?
    # In add_arguments, it adds 'addrport'.
    # In handle, it calls:
    #   addr, port = parse_addr_port(options['addrport'])
    #   self.addr = addr
    #   self.port = port
    
    from django.core.management.utils import parse_addr_port
    
    addr, port = parse_addr_port(args.addrport)
    
    # This is the crucial part: what does parse_addr_port return for '0:8000'?
    # If it returns ('0', '8000'), then the URL will be http://0:8000/
    # If it returns ('0.0.0.0', '8000'), then the URL will be http://0.0.0.0:8000/
    
    return addr, port

def main():
    addr, port = get_server_address_output('0:8000')
    
    # According to the issue, when user provides '0:8000', it should be treated 
    # as '0.0.0.0:8000' for display purposes so the link is clickable/valid.
    # The expected correct behavior is that addr becomes '0.0.0.0'.
    
    print(f"Parsed address: '{addr}', port: '{port}'")
    
    # Assert that the address has been normalized to 0.0.0.0
    assert addr == '0.0.0.0', f"Expected address to be '0.0.0.0' but got '{addr}'. The issue is NOT fixed."
    
    print("Check passed: Address is correctly normalized to 0.0.0.0")
    sys.exit(0)

if __name__ == '__main__':
    main()
