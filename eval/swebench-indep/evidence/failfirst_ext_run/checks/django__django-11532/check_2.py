import os
import sys

# Configure Django settings minimally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={},
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        SECRET_KEY='test-secret-key-for-check-only',
    )

django.setup()

from unittest.mock import patch
from django.core.mail import EmailMessage

def check_unicode_dns_handling():
    """
    Checks if Django correctly handles non-ASCII domain names in email Message-ID
    when the email encoding is set to a non-unicode encoding like iso-8859-1.
    
    The issue is that if the hostname contains non-ASCII characters (e.g., "漢字"),
    and the email encoding is iso-8859-1, generating the Message-ID fails because
    the domain part of the Message-ID is not converted to punycode.
    
    Expected behavior: The domain should be converted to punycode (e.g., "xn--p8s937b")
    so that it can be safely encoded in ASCII/iso-8859-1 headers.
    """
    
    # Use a mock for DNS_NAME with non-ASCII characters
    # The example in the issue uses "漢字" which should become "xn--p8s937b" in punycode
    
    with patch("django.core.mail.message.DNS_NAME", "漢字"):
        email = EmailMessage(
            subject='Test Subject',
            body='',
            from_email='from@example.com',
            to=['to@example.com']
        )
        email.encoding = 'iso-8859-1'
        
        try:
            message = email.message()
        except UnicodeEncodeError:
            # If we get a UnicodeEncodeError, the bug is still present
            raise AssertionError("UnicodeEncodeError raised: Domain name was not converted to punycode")
        
        # Check that the Message-ID header exists
        msg_id = message['Message-ID']
        assert msg_id is not None, "Message-ID header is missing"
        
        # Check that the Message-ID contains the punycode version of the domain
        # "漢字" in punycode is "xn--p8s937b"
        assert 'xn--p8s937b' in msg_id, f"Expected punycode domain 'xn--p8s937b' in Message-ID, but got: {msg_id}"
        
        # Also verify that the Message-ID is valid ASCII (since it's used in headers)
        try:
            msg_id.encode('ascii')
        except UnicodeEncodeError:
            raise AssertionError(f"Message-ID is not ASCII encodable: {msg_id}")

if __name__ == '__main__':
    try:
        check_unicode_dns_handling()
        print("Check passed: Non-ASCII domain names are correctly handled in email Message-ID.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Check failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
