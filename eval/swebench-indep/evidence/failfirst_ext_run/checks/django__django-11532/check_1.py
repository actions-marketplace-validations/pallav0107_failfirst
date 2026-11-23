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
        USE_TZ=True,
    )
    django.setup()

from unittest.mock import patch
from django.core.mail import EmailMessage

def main():
    # The issue states that when DNS_NAME contains non-ASCII characters (e.g., "漢字")
    # and the email encoding is set to iso-8859-1, creating the message should not crash.
    # Instead, the domain part of the Message-ID should be converted to punycode.
    
    # We mock DNS_NAME to simulate a hostname with non-ASCII characters.
    # The expected punycode for "漢字" is "xn--p8s937b" (as suggested in the issue description test case, 
    # though strictly speaking "漢字" punycode is xn--p8s937b? Let's verify logic rather than exact string if possible, 
    # but the issue provides specific expectation).
    # Actually, let's just ensure it doesn't crash and contains valid ASCII in Message-ID header.
    
    try:
        with patch("django.core.mail.message.DNS_NAME", "漢字"):
            email = EmailMessage('subject', '', 'from@example.com', ['to@example.com'])
            email.encoding = 'iso-8859-1'
            message = email.message()
            
            msg_id = message['Message-ID']
            
            # The Message-ID must be ASCII-only because email headers generally require ASCII 
            # or encoded words, but Message-ID specifically should be ASCII.
            # If the fix is applied, the domain part will be punycode (ASCII).
            
            # Check 1: No exception was raised (already passed if we are here)
            
            # Check 2: The Message-ID header exists
            assert msg_id is not None, "Message-ID header is missing"
            
            # Check 3: The Message-ID should be encodable as ASCII without errors
            # This is the core of the fix: non-ASCII domains must be converted to punycode
            try:
                msg_id.encode('ascii')
            except UnicodeEncodeError:
                raise AssertionError("Message-ID contains non-ASCII characters, meaning the domain was not converted to punycode.")
            
            # Check 4: Verify that the punycode representation is present if we know the input
            # The input domain is "漢字". The punycode for "漢字" is indeed "xn--p8s937b" ? 
            # Let's check standard library behavior.
            import encodings.idna
            # "漢字".encode('idna') -> b'xn--p8s937b'
            # So the Message-ID should contain "xn--p8s937b"
            assert 'xn--p8s937b' in msg_id, f"Expected punycode 'xn--p8s937b' in Message-ID, but got: {msg_id}"
            
    except Exception as e:
        print(f"Test failed with exception: {e}", file=sys.stderr)
        sys.exit(1)
        
    print("Test passed: Non-ASCII domain handled correctly via punycode.", file=sys.stderr)
    sys.exit(0)

if __name__ == '__main__':
    main()
