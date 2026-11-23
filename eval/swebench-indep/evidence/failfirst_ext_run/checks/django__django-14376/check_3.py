import sys
import os

# Configure Django settings before importing django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

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
                'PORT': '3306',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
    )
    django.setup()

def check_mysql_backend_kwargs():
    """
    Check if the MySQL backend uses the non-deprecated 'database' and 'password'
    kwargs instead of the deprecated 'db' and 'passwd'.
    """
    from django.db.backends.mysql.base import DatabaseWrapper
    
    # Create a dummy connection settings dict similar to what Django would pass
    # We inspect the get_new_connection method or the _connect_args logic
    
    # The issue points to specific lines in base.py where conn_params are built.
    # In newer fixed versions, it should use 'database' and 'password'.
    # In older broken versions, it uses 'db' and 'passwd'.
    
    # Let's look at the source code of the relevant method or attribute directly
    # since we can't easily connect to a real DB without a server running.
    
    import inspect
    from django.db.backends.mysql.base import DatabaseWrapper
    
    # Get the source code of the get_new_connection method or the part where 
    # conn_params are prepared.
    # Actually, the issue mentions lines 202-205 in base.py.
    # Let's inspect the `get_new_connection` method or `_cursor` or wherever 
    # the connection parameters are constructed.
    
    # In Django's MySQL backend, the `get_new_connection` method calls 
    # `Database.connect(**conn_params)`. The `conn_params` are prepared in 
    # `get_connection_params`.
    
    try:
        wrapper = DatabaseWrapper(settings.DATABASES['default'])
        conn_params = wrapper.get_connection_params()
        
        # Check if the deprecated keys are present
        has_deprecated_db = 'db' in conn_params
        has_deprecated_passwd = 'passwd' in conn_params
        
        # Check if the new keys are present
        has_new_database = 'database' in conn_params
        has_new_password = 'password' in conn_params
        
        # The fix should ensure that 'database' and 'password' are used,
        # and 'db' and 'passwd' are NOT used.
        
        # If the fix is applied:
        # - 'db' should NOT be in conn_params
        # - 'passwd' should NOT be in conn_params
        # - 'database' SHOULD be in conn_params
        # - 'password' SHOULD be in conn_params
        
        assert not has_deprecated_db, "Deprecated 'db' key found in connection parameters"
        assert not has_deprecated_passwd, "Deprecated 'passwd' key found in connection parameters"
        assert has_new_database, "New 'database' key missing from connection parameters"
        assert has_new_password, "New 'password' key missing from connection parameters"
        
        return True
        
    except Exception as e:
        # If we can't even get this far, something is wrong
        raise AssertionError(f"Failed to check connection parameters: {e}")

if __name__ == '__main__':
    try:
        check_mysql_backend_kwargs()
        print("Check passed: MySQL backend uses correct kwargs.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Check failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
