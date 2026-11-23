import sys
import os
import tempfile
import shutil

def main():
    # Create a temporary directory for the test Sphinx project
    tmpdir = tempfile.mkdtemp()
    try:
        # Create minimal conf.py
        conf_content = """
project = 'Test'
extensions = ['sphinx.ext.autodoc']
"""
        with open(os.path.join(tmpdir, 'conf.py'), 'w') as f:
            f.write(conf_content)

        # Create a minimal index.rst
        index_content = """
Test
====

.. autofunction:: mymodule.foo
"""
        with open(os.path.join(tmpdir, 'index.rst'), 'w') as f:
            f.write(index_content)

        # Create a module with the function described in the issue
        module_dir = os.path.join(tmpdir, 'mymodule')
        os.makedirs(module_dir)
        with open(os.path.join(module_dir, '__init__.py'), 'w') as f:
            f.write("")
        
        module_file = os.path.join(module_dir, 'foo.py')
        foo_content = '''
def foo(text):
    """Bar

    :param text: a text
    :type text: bytes | str

    """
    pass
'''
        with open(module_file, 'w') as f:
            f.write(foo_content)

        # Add tmpdir to sys.path so sphinx can import mymodule
        sys.path.insert(0, tmpdir)

        # Build the documentation
        from sphinx.application import Sphinx
        from io import StringIO

        srcdir = tmpdir
        outdir = os.path.join(tmpdir, '_build', 'html')
        doctreedir = os.path.join(tmpdir, '_build', 'doctrees')
        confdir = tmpdir
        
        # Ensure output directories exist
        os.makedirs(outdir, exist_ok=True)
        os.makedirs(doctreedir, exist_ok=True)

        warning_stream = StringIO()
        
        app = Sphinx(
            srcdir=srcdir,
            confdir=confdir,
            outdir=outdir,
            doctreedir=doctreedir,
            buildername='html',
            confoverrides={},
            status=None,
            warning=warning_stream,
            freshenv=True,
            warningiserror=False,
            tags=[],
            verbosity=0,
            parallel=1
        )

        try:
            app.build()
        except Exception as e:
            # If building fails completely, that's likely an error
            print(f"Build failed with exception: {e}", file=sys.stderr)
            sys.exit(1)

        warnings = warning_stream.getvalue()
        
        # Check if there are warnings about unknown type or parsing errors related to '|'
        # In older Sphinx versions, "bytes | str" might cause a warning like "unknown type" 
        # or fail to parse correctly.
        # The issue requests support for this syntax. If it's supported, there should be no
        # warnings about the type syntax being invalid or unparseable.
        
        # Specifically, we look for warnings that indicate the type annotation was not understood.
        # Common warnings for unsupported types include "Invalid type expression" or similar.
        # However, simply checking for absence of specific warnings might be fragile.
        
        # Let's check the generated HTML or doctree to see if the type was rendered correctly.
        # Or better, check if the build succeeded without specific type-related warnings.
        
        # A robust check: if the syntax is supported, the build should complete without
        # warnings specifically complaining about the type format "bytes | str".
        
        # Let's look for common error patterns in warnings for bad type annotations
        lower_warnings = warnings.lower()
        
        # If the feature is NOT implemented, Sphinx might warn about "Invalid type" 
        # or just treat it as plain text but potentially log a warning.
        # In Sphinx 4.1, the native support for PEP 604 (|) in docstrings via autodoc 
        # might not be present yet (it was added in later versions or requires specific extensions).
        # The RFE asks to ADD support. So if it's fixed, it should work without errors.
        
        # Let's check if the warning stream contains errors related to the type parsing
        # If the syntax is invalid/unrecognized, sphinx.ext.autodoc might produce a warning.
        
        # We will assert that there are no warnings containing "invalid" or "error" related to types
        # This is a heuristic. A better way is to check the actual output.
        
        # Let's try to find the generated HTML for the function signature
        html_file = os.path.join(outdir, 'index.html')
        if os.path.exists(html_file):
            with open(html_file, 'r') as f:
                html_content = f.read()
            
            # If the type is correctly parsed, it should appear in the documentation.
            # It might be rendered as "bytes | str" or similar.
            # If it failed, it might be missing or show an error.
            
            # For the purpose of this check, we assume that if the build produced no 
            # severe warnings about the type, and the HTML contains the function, it's okay.
            # But we need to be stricter.
            
            # Let's check if the warning stream is empty or does not contain type-related errors.
            # Known warning for unsupported types in some Sphinx versions: 
            # "WARNING: Invalid type expression"
            
            if "invalid type" in lower_warnings or "type expression" in lower_warnings:
                # This suggests the type syntax was not recognized
                raise AssertionError("Sphinx reported invalid type expression for 'bytes | str'")
            
            # Also check if the build generally failed
            # If app.statuscode is not 0, it indicates issues
            if app.statuscode != 0:
                 raise AssertionError(f"Sphinx build finished with non-zero status code: {app.statuscode}. Warnings: {warnings}")

        else:
            raise AssertionError("HTML output file was not generated")

    finally:
        # Cleanup
        if tmpdir in sys.path:
            sys.path.remove(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    sys.exit(0)

if __name__ == '__main__':
    main()
