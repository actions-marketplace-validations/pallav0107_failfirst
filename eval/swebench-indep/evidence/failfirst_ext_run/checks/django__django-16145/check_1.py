import sys
import os

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
from django.core.management.base import CommandParser

def get_server_address(addrport):
    """
    Simulate the logic in runserver command to determine the displayed address.
    We inspect how the command parses the addrport and what it considers the 'url'.
    """
    cmd = RunserverCommand()
    
    # Create a parser to parse the argument like the real command does
    parser = CommandParser()
    cmd.add_arguments(parser)
    
    # Parse the arguments
    options = parser.parse_args([addrport])
    
    # The runserver command stores the parsed address in options.addrport
    # But we need to check what URL it constructs for display.
    # In Django 4.2, the logic is roughly:
    # addr, port = handle_default_port(options.addrport)
    # if addr == '0': addr = '0.0.0.0' (for binding)
    # But the display URL might still use the original '0' if not handled correctly.
    
    # Let's look at the actual method that generates the URL message.
    # In django/core/management/commands/runserver.py, there is a method 
    # or logic in handle() that prints "Starting development server at http://%s/" % self.url
    
    # The `url` property or variable is constructed from the bound address.
    # Let's trace the code path.
    
    # In Django 4.2, the relevant code in runserver.py handle():
    # ...
    # addr, port = self.handle_default_port(options.addrport)
    # ...
    # self.url = 'http://%s:%s/' % (addr, port)
    # ...
    # self.stdout.write("Starting development server at %s" % self.url)
    
    # And handle_default_port:
    # def handle_default_port(self, addrport):
    #     ...
    #     if addr == '0':
    #         addr = '0.0.0.0'
    #     return addr, int(port)
    
    # So if the fix is applied, passing '0:8000' should result in addr being '0.0.0.0'
    # in the final URL.
    
    # We can call handle_default_port directly to test this logic.
    addr, port = cmd.handle_default_port(addrport)
    
    return f"http://{addr}:{port}/"

def main():
    # Test case from the issue: "0:8000" should display as "http://0.0.0.0:8000/"
    test_input = "0:8000"
    expected_url = "http://0.0.0.0:8000/"
    
    actual_url = get_server_address(test_input)
    
    print(f"Input: {test_input}")
    print(f"Expected URL: {expected_url}")
    print(f"Actual URL: {actual_url}")
    
    assert actual_url == expected_url, f"URL mismatch: expected '{expected_url}', got '{actual_url}'"
    
    # Also verify that explicit 0.0.0.0 still works correctly
    test_input_2 = "0.0.0.0:8000"
    expected_url_2 = "http://0.0.0.0:8000/"
    actual_url_2 = get_server_address(test_input_2)
    assert actual_url_2 == expected_url_2, f"URL mismatch for explicit 0.0.0.0: expected '{expected_url_2}', got '{actual_url_2}'"

    print("All checks passed.")
    sys.exit(0)

if __name__ == '__main__':
    main()
