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
                'USER': 'test_user',
                'PASSWORD': 'test_password',
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
    Check if the MySQL backend uses the deprecated 'db' and 'passwd' kwargs
    or the new 'database' and 'password' kwargs.
    
    The issue states that mysqlclient has deprecated 'db' and 'passwd' in favor
    of 'database' and 'password'. We need to verify that Django's MySQL backend
    uses the non-deprecated parameter names.
    """
    from django.db.backends.mysql.base import DatabaseWrapper
    
    # Create a dummy connection parameters dict similar to what would be passed
    # We inspect the get_connection_params method or the __init__ logic
    
    # Let's look at the source code of the relevant method to see which keys are used
    import inspect
    from django.db.backends.mysql.base import DatabaseWrapper
    
    # Get the source code of the get_connection_params method
    try:
        source = inspect.getsource(DatabaseWrapper.get_connection_params)
    except Exception as e:
        # If we can't get source, try to find the file and read it
        import django.db.backends.mysql.base as mysql_base
        source_file = mysql_base.__file__
        with open(source_file, 'r') as f:
            content = f.read()
        # Find the get_connection_params method
        import re
        match = re.search(r'def get_connection_params\(self\):.*?(?=\n    def |\nclass |\Z)', content, re.DOTALL)
        if match:
            source = match.group(0)
        else:
            raise AssertionError("Could not find get_connection_params method")

    # Check if deprecated parameters are used
    # The issue mentions lines around 202-205 in base.py
    # Deprecated: 'db' and 'passwd'
    # New: 'database' and 'password'
    
    # We should NOT see 'db'='...' or 'passwd'='...' being set in the returned dict
    # Instead we should see 'database' and 'password'
    
    # Let's check for the presence of deprecated keys in the connection params construction
    # Look for patterns like "'db': self.settings_dict['NAME']" or "'passwd': ..."
    
    has_deprecated_db = "'db'" in source or '"db"' in source
    has_deprecated_passwd = "'passwd'" in source or '"passwd"' in source
    
    # Also check for the correct new keys
    has_new_database = "'database'" in source or '"database"' in source
    has_new_password = "'password'" in source or '"password"' in source
    
    # The fix should replace 'db' with 'database' and 'passwd' with 'password'
    # So we assert that deprecated keys are NOT used and new keys ARE used
    
    # However, we need to be careful: the settings dict might use 'NAME' and 'PASSWORD'
    # but the kwargs passed to mysqlclient should be 'database' and 'password'
    
    # Let's verify more precisely by checking if the deprecated kwargs are being passed
    # to the connect function
    
    # A more robust check: instantiate a wrapper and see what params it generates
    # But we can't actually connect. Let's stick to source inspection.
    
    # According to the issue, the bug is that 'db' and 'passwd' are used.
    # After fix, 'database' and 'password' should be used.
    
    # Assert that deprecated parameters are not present in the connection params logic
    # We look specifically in the get_connection_params method
    
    # Filter out comments and strings that might falsely match
    # Simple check: if 'db' key is assigned in the returned dict, it's wrong
    
    # Let's parse more carefully
    lines = source.split('\n')
    found_db_kwarg = False
    found_passwd_kwarg = False
    found_database_kwarg = False
    found_password_kwarg = False
    
    for line in lines:
        stripped = line.strip()
        # Skip comments
        if stripped.startswith('#'):
            continue
        # Check for dictionary key assignments
        if "'db':" in stripped or '"db":' in stripped:
            found_db_kwarg = True
        if "'passwd':" in stripped or '"passwd":' in stripped:
            found_passwd_kwarg = True
        if "'database':" in stripped or '"database":' in stripped:
            found_database_kwarg = True
        if "'password':" in stripped or '"password":' in stripped:
            found_password_kwarg = True
            
    # The correct behavior (fixed) should NOT have db/passwd and SHOULD have database/password
    assert not found_db_kwarg, "Deprecated 'db' kwarg is still being used in MySQL backend"
    assert not found_passwd_kwarg, "Deprecated 'passwd' kwarg is still being used in MySQL backend"
    assert found_database_kwarg, "New 'database' kwarg is not being used in MySQL backend"
    assert found_password_kwarg, "New 'password' kwarg is not being used in MySQL backend"

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
