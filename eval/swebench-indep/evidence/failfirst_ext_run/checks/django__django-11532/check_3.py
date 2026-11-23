import os
import sys

# Configure Django settings minimally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysettings')

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
        DEFAULT_CHARSET='utf-8',
    )

django.setup()

from unittest.mock import patch
from django.core.mail import EmailMessage

def main():
    # The issue states that when DNS_NAME contains non-ASCII characters (e.g., "漢字")
    # and the email encoding is set to iso-8859-1, generating the message crashes
    # because the Message-ID header cannot be encoded.
    # The fix should convert the domain part of the Message-ID to punycode.
    
    # We mock DNS_NAME to simulate a hostname with non-ASCII characters.
    # Note: The issue description mentions patching "django.core.mailmessage.DNS_NAME",
    # but the correct path is likely "django.core.mail.message.DNS_NAME" or similar.
    # Looking at standard Django structure, DNS_NAME is usually in django.core.mail.utils or message.
    # In Django 3.0, DNS_NAME is defined in django.core.mail.message.
    
    try:
        with patch("django.core.mail.message.DNS_NAME", "漢字"):
            email = EmailMessage('subject', '', 'from@example.com', ['to@example.com'])
            email.encoding = 'iso-8859-1'
            
            # This call should trigger the generation of the Message-ID header
            # using the mocked DNS_NAME. If the bug exists, this will raise
            # UnicodeEncodeError. If fixed, it should succeed and contain punycode.
            message = email.message()
            
            msg_id = message['Message-ID']
            
            # The fix requires converting the non-ASCII domain to punycode.
            # "漢字" in punycode is "xn--p8s937b" (approximately, depending on exact encoding logic).
            # The issue explicitly checks for 'xn--p8s937b' in the Message-ID.
            assert 'xn--p8s937b' in msg_id, f"Expected punycode domain in Message-ID, got: {msg_id}"
            
    except UnicodeEncodeError as e:
        print(f"Bug reproduced: UnicodeEncodeError occurred: {e}", file=sys.stderr)
        sys.exit(1)
    except AssertionError as e:
        print(f"Bug reproduced: Assertion failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Test passed: Non-ASCII domain handled correctly via punycode.")
    sys.exit(0)

if __name__ == '__main__':
    main()
