import sys
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Ensure we can import sphinx
import sphinx
from sphinx.application import Sphinx
from sphinx.util import logging

def main():
    # Create a temporary directory for the test project
    tmpdir = tempfile.mkdtemp()
    srcdir = os.path.join(tmpdir, 'source')
    outdir = os.path.join(tmpdir, 'build')
    doctreedir = os.path.join(outdir, '.doctrees')
    
    os.makedirs(srcdir)
    
    # Create conf.py
    conf_content = """
project = 'Test'
extensions = []
linkcheck_anchors = True
linkcheck_timeout = 5
"""
    with open(os.path.join(srcdir, 'conf.py'), 'w') as f:
        f.write(conf_content)
        
    # Create index.rst with a link that would return 404 if accessed
    # We use a dummy URL since we have no network access. 
    # The key is to mock the request to simulate a 404 error.
    index_content = """
Test
====

`foo <http://example.com/nonexistent#anchor>`_
"""
    with open(os.path.join(srcdir, 'index.rst'), 'w') as f:
        f.write(index_content)

    try:
        # Mock the requests library to simulate a 404 response
        import requests
        
        def mock_get(url, **kwargs):
            response = MagicMock()
            response.status_code = 404
            response.reason = 'Not Found'
            response.url = url
            response.headers = {}
            response.content = b''
            response.text = ''
            # Raise an HTTPError to simulate what requests does on bad status
            response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error: Not Found for url: " + url)
            return response

        with patch('sphinx.builders.linkcheck.requests.get', side_effect=mock_get):
            # Also need to handle head requests if used
            with patch('sphinx.builders.linkcheck.requests.head', side_effect=mock_get):
                app = Sphinx(
                    srcdir=srcdir,
                    confdir=srcdir,
                    outdir=outdir,
                    doctreedir=doctreedir,
                    buildername='linkcheck',
                    freshenv=True,
                    warningiserror=False,
                    verbosity=0
                )
                
                # Capture warnings/output
                from io import StringIO
                warning_stream = StringIO()
                app._warning = warning_stream
                
                try:
                    app.build()
                except Exception as e:
                    # Build might fail due to mocking issues, but we care about the check result
                    pass

                # Check the output
                # The issue states that when linkcheck_anchors is True and server returns 404,
                # it should report "404 Client Error..." instead of "Anchor ... not found"
                
                # In Sphinx 3.3, the linkcheck builder writes results to stdout or log.
                # Let's look at the app's status or the warning stream.
                # Actually, linkcheck prints to stdout usually.
                
                # Let's re-run build capturing stdout
                from contextlib import redirect_stdout
                stdout_capture = StringIO()
                
                # Reset and rebuild
                app = Sphinx(
                    srcdir=srcdir,
                    confdir=srcdir,
                    outdir=outdir,
                    doctreedir=doctreedir,
                    buildername='linkcheck',
                    freshenv=True,
                    warningiserror=False,
                    verbosity=0
                )
                
                with redirect_stdout(stdout_capture):
                    try:
                        app.build()
                    except:
                        pass
                        
                output = stdout_capture.getvalue()
                
                # If the bug is present, output contains "Anchor 'anchor' not found"
                # If fixed, it should contain "404" or similar error message
                
                print("Output:", output)
                
                # Assert that the correct behavior is present (issue is fixed)
                # Expected: "404 Client Error"
                # Buggy: "Anchor 'anchor' not found"
                
                assert "Anchor 'anchor' not found" not in output, \
                    "Bug is present: reported 'Anchor not found' instead of HTTP error"
                
                assert "404" in output, \
                    "Expected 404 error message in output"
                    
    finally:
        shutil.rmtree(tmpdir)

if __name__ == '__main__':
    main()
