import sys
import os

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'test_db',
                'USER': 'root',
                'PASSWORD': 'password',
                'HOST': 'localhost',
                'PORT': 3306,
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )

django.setup()

from django.db.backends.mysql.base import DatabaseWrapper

def check_deprecated_kwargs():
    """
    Check if the MySQL backend uses deprecated 'db' and 'passwd' kwargs
    instead of the new 'database' and 'password' kwargs.
    
    The issue states that mysqlclient has deprecated 'db' and 'passwd' in favor
    of 'database' and 'password'. We need to verify that Django's MySQL backend
    uses the new parameter names.
    """
    # Create a database wrapper instance with test settings
    db_wrapper = DatabaseWrapper(settings.DATABASES['default'])
    
    # Get the connection parameters that would be passed to mysqlclient
    # The get_connection_params method prepares the arguments for the MySQL client
    try:
        conn_params = db_wrapper.get_connection_params()
    except Exception as e:
        # If we can't get connection params due to missing MySQL server or other issues,
        # we should still be able to inspect the code logic
        print(f"Warning: Could not get connection params: {e}")
        # Fall back to checking the source code directly
        return check_source_code()
    
    # Check if deprecated keys are present
    has_deprecated_db = 'db' in conn_params
    has_deprecated_passwd = 'passwd' in conn_params
    
    # Check if new keys are present
    has_new_database = 'database' in conn_params
    has_new_password = 'password' in conn_params
    
    # The fix is correct if:
    # 1. Deprecated keys ('db', 'passwd') are NOT used
    # 2. New keys ('database', 'password') ARE used
    
    # Assert that deprecated keys are not present
    assert not has_deprecated_db, "Deprecated 'db' key found in connection parameters"
    assert not has_deprecated_passwd, "Deprecated 'passwd' key found in connection parameters"
    
    # Assert that new keys are present
    assert has_new_database, "New 'database' key not found in connection parameters"
    assert has_new_password, "New 'password' key not found in connection parameters"
    
    return True

def check_source_code():
    """
    Fallback: Check the source code directly if we can't instantiate the wrapper.
    This reads the base.py file and checks for usage of deprecated parameters.
    """
    import inspect
    from django.db.backends.mysql import base
    
    # Get the source code of the DatabaseWrapper class
    source = inspect.getsource(base)
    
    # Check for deprecated parameter usage in get_connection_params or similar methods
    # Look for patterns like "'db':" or "'passwd':" which indicate deprecated usage
    has_deprecated_db_usage = "'db':" in source or '"db":' in source
    has_deprecated_passwd_usage = "'passwd':" in source or '"passwd":' in source
    
    # Also check that new parameters are used
    has_new_database_usage = "'database':" in source or '"database":' in source
    has_new_password_usage = "'password':" in source or '"password":' in source
    
    # The fix is correct if deprecated usages are removed and new ones are added
    assert not has_deprecated_db_usage, "Source code still contains deprecated 'db' parameter usage"
    assert not has_deprecated_passwd_usage, "Source code still contains deprecated 'passwd' parameter usage"
    
    return True

if __name__ == '__main__':
    try:
        check_deprecated_kwargs()
        print("PASS: MySQL backend does not use deprecated 'db' and 'passwd' kwargs")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(1)
