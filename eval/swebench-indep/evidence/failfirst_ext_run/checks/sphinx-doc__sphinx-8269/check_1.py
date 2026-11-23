import sys
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Ensure the repository root is in the path if needed, though usually not necessary
# if installed. We assume standard import works.

def main():
    # Create a temporary directory for the Sphinx project
    tmpdir = tempfile.mkdtemp()
    srcdir = os.path.join(tmpdir, 'source')
    outdir = os.path.join(tmpdir, 'build')
    
    try:
        os.makedirs(srcdir)
        
        # Create conf.py
        with open(os.path.join(srcdir, 'conf.py'), 'w') as f:
            f.write("project = 'Test'\n")
            f.write("extensions = []\n")
            f.write("linkcheck_anchors = True\n") # Default is True, but explicit
            
        # Create index.rst with a broken link (404) and an anchor
        with open(os.path.join(srcdir, 'index.rst'), 'w') as f:
            f.write("Test\n====\n\n")
            f.write("`Link <https://example.com/nonexistent#anchor>`_\n")
            
        # Import Sphinx components
        from sphinx.application import Sphinx
        from sphinx.util.console import colorize
        
        # We need to mock the network request because we have no network access.
        # The issue is about how the result is reported when an HTTP error occurs.
        # We simulate a 404 response.
        
        import requests
        from requests.exceptions import HTTPError
        
        # Mock response object
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.url = "https://example.com/nonexistent"
        mock_response.headers = {}
        mock_response.is_redirect = False
        
        # Raise HTTPError on raise_for_status to simulate requests behavior
        def raise_for_status():
            raise HTTPError(f"404 Client Error: Not Found for url: {mock_response.url}", response=mock_response)
            
        mock_response.raise_for_status = raise_for_status
        
        # Patch requests.get to return our mock
        with patch('sphinx.builders.linkcheck.requests.get', return_value=mock_response) as mock_get:
            # Also patch head if used, but linkcheck usually uses get for anchors
            with patch('sphinx.builders.linkcheck.requests.head', return_value=mock_response):
                
                app = Sphinx(
                    srcdir=srcdir,
                    confdir=srcdir,
                    outdir=os.path.join(outdir, 'html'),
                    doctreedir=os.path.join(outdir, 'doctrees'),
                    buildername='linkcheck',
                    freshenv=True,
                    warningiserror=False,
                    verbosity=0
                )
                
                # Build
                app.build()
                
                # Check the output/warnings
                # The linkcheck builder writes results to stdout/stderr or log.
                # In Sphinx 3.x, linkcheck outputs to the console via logging.
                # We can check the app._warning content or capture logs.
                
                # Let's look at the status code handling in the builder directly if possible,
                # or parse the warning stream.
                
                warnings = app._warning.getvalue()
                
                # The issue states that currently it says "Anchor 'test' not found"
                # But it SHOULD say "404 Client Error..."
                
                # If the bug is present, the warning will contain "Anchor"
                # If the bug is fixed, the warning will contain "404" or "Client Error"
                
                # Note: The exact text might vary slightly, but the distinction is clear.
                
                print("Warnings captured:")
                print(warnings)
                
                # Assert that the error message reflects the HTTP error, not just the missing anchor
                # If fixed, it should mention 404 or Client Error.
                # If broken, it mentions Anchor not found.
                
                if "404" in warnings or "Client Error" in warnings:
                    # Behavior is correct (fixed)
                    print("SUCCESS: Linkcheck correctly reports HTTP error.")
                    sys.exit(0)
                elif "Anchor" in warnings and "not found" in warnings:
                    # Behavior is incorrect (bug present)
                    print("FAILURE: Linkcheck incorrectly reports Anchor not found instead of HTTP error.")
                    assert False, "Bug still present: Reported 'Anchor not found' instead of HTTP 404 error"
                else:
                    # Unexpected output
                    print(f"UNEXPECTED: Could not determine status from warnings: {warnings}")
                    # If it's broken link, it should be in warnings.
                    # If it worked, it wouldn't be broken. But we mocked 404.
                    # So it must be reported as broken.
                    assert False, "Unexpected output format"

    finally:
        shutil.rmtree(tmpdir)

if __name__ == '__main__':
    main()
