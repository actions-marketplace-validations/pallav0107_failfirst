import sys
import tempfile
import os

def main():
    # Create a temporary directory for the test module and sphinx build
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a Python module with a generic-typed class that triggers the bug
        # The bug is in sphinx.ext.autodoc.mock._make_subclass where it tries to
        # concatenate str + TypeVar.
        
        module_code = '''
from typing import Generic, TypeVar

T = TypeVar('T')

class MyGenericClass(Generic[T]):
    """A simple generic class."""
    def __init__(self, value: T):
        self.value = value
        
    def get_value(self) -> T:
        return self.value
'''
        
        module_path = os.path.join(tmpdir, 'my_generic_module.py')
        with open(module_path, 'w') as f:
            f.write(module_code)
            
        # Add tmpdir to sys.path so we can import the module
        sys.path.insert(0, tmpdir)
        
        try:
            # Import the module to ensure it's valid Python
            import my_generic_module
            
            # 2. Set up a minimal Sphinx application to test autodoc
            # We need to trigger the mocking mechanism if the module has dependencies
            # that are not installed, or simply force autodoc to process the generic class.
            # However, the bug report mentions `mock._make_subclass`. This is typically
            # invoked when autodoc needs to mock a base class that is not available.
            
            # To reliably reproduce the specific error "concatenate a str to a TypeVar",
            # we need to look at how sphinx.ext.autodoc.mock works.
            # In Sphinx 3.x, autodoc uses unittest.mock to mock objects.
            # The issue arises when autodoc inspects a class with generic bases.
            
            # Let's try to use sphinx.ext.autodoc directly on this class.
            from sphinx.ext.autodoc import ClassDocumenter
            from sphinx.application import Sphinx
            from sphinx.util.docutils import docutils_namespace
            
            # Create a minimal conf.py content
            conf_content = '''
project = 'Test'
extensions = ['sphinx.ext.autodoc']
'''
            conf_path = os.path.join(tmpdir, 'conf.py')
            with open(conf_path, 'w') as f:
                f.write(conf_content)
                
            srcdir = tmpdir
            outdir = os.path.join(tmpdir, '_build', 'html')
            doctreedir = os.path.join(tmpdir, '_build', 'doctrees')
            confoverrides = {}
            
            # Initialize Sphinx app
            with docutils_namespace():
                app = Sphinx(
                    srcdir=srcdir,
                    confdir=srcdir,
                    outdir=outdir,
                    doctreedir=doctreedir,
                    buildername='html',
                    confoverrides=confoverrides,
                    status=None,
                    warning=None,
                    freshenv=True,
                    warningiserror=False,
                    tags=[],
                    verbosity=0,
                    parallel=1
                )
                
                # Now, let's try to document the class.
                # We can use the autodoc extension's machinery.
                # A direct way is to call generate() on a ClassDocumenter.
                
                # First, we need to get the directive and state.
                # This is complex. Alternatively, we can just try to build the docs
                # for a simple rst file that references this class.
                
                index_rst = '''
Test
====

.. autoclass:: my_generic_module.MyGenericClass
   :members:
'''
                index_path = os.path.join(tmpdir, 'index.rst')
                with open(index_path, 'w') as f:
                    f.write(index_rst)
                    
                # Try to build
                try:
                    app.build(force_all=True)
                    # If we get here, the build succeeded
                    print("Build succeeded.")
                    sys.exit(0)
                except TypeError as e:
                    # Check if it's the specific error mentioned
                    if "can only concatenate str" in str(e) or "TypeVar" in str(e):
                        print(f"Caught expected TypeError: {e}")
                        sys.exit(1)
                    else:
                        # Some other TypeError, might be unrelated but still a failure
                        print(f"Caught unexpected TypeError: {e}")
                        sys.exit(1)
                except Exception as e:
                    print(f"Caught unexpected exception: {type(e).__name__}: {e}")
                    sys.exit(1)
                    
        finally:
            # Clean up sys.path
            if tmpdir in sys.path:
                sys.path.remove(tmpdir)

if __name__ == '__main__':
    main()
