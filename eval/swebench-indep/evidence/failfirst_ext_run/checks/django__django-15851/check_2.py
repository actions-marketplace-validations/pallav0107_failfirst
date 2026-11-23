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
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'testdb',
                'USER': 'testuser',
                'PASSWORD': 'testpass',
                'HOST': 'localhost',
                'PORT': '5432',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )

django.setup()

from django.db import connections
from django.db.backends.postgresql.client import DatabaseClient

def check_dbshell_args_order():
    """
    Check if the PostgreSQL dbshell passes additional parameters before the dbname.
    
    The issue states that psql expects all options to precede the database name.
    If extra args like '-c' are passed after the dbname, psql ignores them.
    
    We inspect the get_command_line_args method or simulate the argument construction
    to verify the order.
    """
    connection = connections['default']
    client = DatabaseClient(connection)
    
    # Simulate passing extra arguments like ['-c', 'select 1;']
    extra_args = ['-c', 'select 1;']
    
    # Get the command line arguments that would be passed to psql
    # In Django 4.2, the DatabaseClient class has a method to construct these args
    # Let's look at how args are constructed
    
    # The key is to check if the database name comes AFTER the extra args
    # We need to inspect the internal logic or call the relevant method
    
    # In django/db/backends/postgresql/client.py, the runshell method constructs args
    # Let's trace through the logic by examining what args would be generated
    
    # For PostgreSQL, the args typically look like:
    # ['psql', option1, option2, ..., dbname]
    # Extra args from -- should be inserted before dbname
    
    # Let's create a test to verify the order
    # We'll monkey-patch or inspect the args construction
    
    # Actually, let's look at the source code behavior directly
    # The runshell method in DatabaseClient builds args_list
    
    # In Django 4.2, the relevant code in django/db/backends/postgresql/client.py:
    # def runshell(self, parameters):
    #     args = [self.executable_name]
    #     ... add options ...
    #     args.append(self.connection.settings_dict['NAME'])  # dbname added here
    #     
    # If extra parameters are passed via --, they need to be before the dbname
    
    # Let's check if there's a way to get the args without running psql
    # We can examine the get_command_line_args or similar
    
    # Looking at the implementation, we need to verify that when extra_args are provided,
    # they appear before the database name in the final argument list
    
    # Let's simulate what happens in runshell
    args = ['psql']
    
    # Add standard options (simplified)
    settings_dict = connection.settings_dict
    if settings_dict.get('USER'):
        args.extend(['-U', settings_dict['USER']])
    if settings_dict.get('HOST'):
        args.extend(['-h', settings_dict['HOST']])
    if settings_dict.get('PORT'):
        args.extend(['-p', str(settings_dict['PORT'])])
    
    # This is where extra_args should be inserted, BEFORE the dbname
    # The bug is if extra_args are appended AFTER the dbname
    
    dbname = settings_dict['NAME']
    
    # Correct behavior: extra_args come before dbname
    # Incorrect behavior: extra_args come after dbname
    
    # Let's check the actual implementation by looking at how Django handles this
    # In the fixed version, extra parameters should be inserted before dbname
    
    # We'll check by examining if the code properly handles parameter ordering
    # Since we can't easily intercept runshell without executing psql,
    # let's check the source code logic indirectly
    
    # Import the module and check if the fix is present
    import inspect
    source = inspect.getsource(DatabaseClient.runshell)
    
    # The fix should ensure extra args are placed before the database name
    # Look for the pattern where args are constructed
    
    # In the buggy version, it might look like:
    # args.append(dbname)
    # args.extend(parameters)  # WRONG - params after dbname
    
    # In the fixed version:
    # args.extend(parameters)  # params before dbname  
    # args.append(dbname)
    
    # Or alternatively, parameters are inserted at the right position
    
    # Let's check if 'parameters' (extra args) are handled before dbname is appended
    # We look for the order of operations in the source
    
    # Find where dbname is added and where parameters are used
    lines = source.split('\n')
    
    dbname_line_idx = None
    params_extend_idx = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "args.append" in stripped and ("NAME" in stripped or "dbname" in stripped.lower()):
            dbname_line_idx = i
        if "parameters" in stripped and ("extend" in stripped or "insert" in stripped or "+=" in stripped):
            params_extend_idx = i
    
    # If parameters are processed/added BEFORE dbname is appended, it's correct
    # If parameters are processed/added AFTER dbname is appended, it's incorrect
    
    if params_extend_idx is not None and dbname_line_idx is not None:
        # Parameters should be handled before dbname is appended
        assert params_extend_idx < dbname_line_idx, \
            f"Extra parameters are added after dbname (params at line {params_extend_idx}, dbname at line {dbname_line_idx}). " \
            "This causes psql to ignore the extra arguments."
    elif params_extend_idx is None:
        # If parameters aren't explicitly handled in runshell, check if they're passed differently
        # In some implementations, parameters might be passed via a different mechanism
        # Let's check if the method signature accepts parameters and uses them correctly
        
        # Check if runshell accepts parameters
        sig = inspect.signature(DatabaseClient.runshell)
        if 'parameters' in sig.parameters:
            # It accepts parameters but doesn't seem to use them - that's a bug
            assert False, "runshell accepts parameters but doesn't appear to use them in the source"
        else:
            # Maybe the old signature didn't accept parameters
            assert False, "runshell doesn't accept parameters argument - extra args cannot be passed"
    else:
        # Couldn't determine the order definitively from source inspection
        # Fall back to a different check
        pass
    
    # Additional verification: actually construct the args as the method would
    # and verify the order
    
    # Let's try to call a helper or reconstruct the logic
    # In newer Django versions, there might be a get_command_line_args method
    
    if hasattr(client, 'get_command_line_args'):
        args_list = client.get_command_line_args(extra_args)
        # Find index of dbname and indices of extra args
        dbname_idx = None
        extra_arg_indices = []
        
        for i, arg in enumerate(args_list):
            if arg == dbname:
                dbname_idx = i
            if arg in extra_args:
                extra_arg_indices.append(i)
        
        assert dbname_idx is not None, "Database name not found in args list"
        assert len(extra_arg_indices) == len(extra_args), "Not all extra args found in args list"
        
        # All extra args should come before dbname
        for idx in extra_arg_indices:
            assert idx < dbname_idx, \
                f"Extra argument '{args_list[idx]}' at index {idx} comes after dbname at index {dbname_idx}"
    else:
        # If no get_command_line_args, rely on the source code inspection above
        # which already did the assertion
        pass

if __name__ == '__main__':
    try:
        check_dbshell_args_order()
        print("PASS: Extra parameters are correctly placed before dbname")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
