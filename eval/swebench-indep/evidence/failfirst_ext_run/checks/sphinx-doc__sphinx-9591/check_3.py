import sys
import os
import tempfile
import shutil

def main():
    # Create a temporary directory for the test project
    tmpdir = tempfile.mkdtemp()
    try:
        # Setup minimal Sphinx project structure
        srcdir = os.path.join(tmpdir, 'source')
        outdir = os.path.join(tmpdir, 'build')
        os.makedirs(srcdir)
        
        # Create conf.py
        conf_content = """
project = 'Test'
extensions = ['sphinx.ext.autodoc']
"""
        with open(os.path.join(srcdir, 'conf.py'), 'w') as f:
            f.write(conf_content)
            
        # Create index.rst
        index_content = """
Test
====

.. automodule:: mymod
   :members:
"""
        with open(os.path.join(srcdir, 'index.rst'), 'w') as f:
            f.write(index_content)
            
        # Create the module to be documented
        mod_content = '''
from typing import Optional

class Point:
    """A class representing a point."""
    pass

class Square:
    """A class representing a square figure."""
    
    @property
    def end(self) -> Point:
        """Square's end position (bottom-right corner)."""
        return Point()
'''
        with open(os.path.join(srcdir, 'mymod.py'), 'w') as f:
            f.write(mod_content)
            
        # Add srcdir to sys.path so autodoc can find mymod
        sys.path.insert(0, srcdir)
        
        try:
            from sphinx.application import Sphinx
            from sphinx.util.docutils import docutils_namespace
            
            # Build the docs
            with docutils_namespace():
                app = Sphinx(
                    srcdir=srcdir,
                    confdir=srcdir,
                    outdir=outdir,
                    doctreedir=os.path.join(outdir, '.doctrees'),
                    buildername='html',
                    freshenv=True,
                    warningiserror=False,
                    verbosity=0
                )
                app.build()
            
            # Check the generated HTML for cross-references
            html_file = os.path.join(outdir, 'index.html')
            if not os.path.exists(html_file):
                print("ERROR: HTML file was not generated")
                sys.exit(1)
                
            with open(html_file, 'r') as f:
                html_content = f.read()
                
            # The issue is that cross-references in property type annotations don't work.
            # If fixed, the type annotation "Point" should be linked to the Point class documentation.
            # We look for a reference to Point in the context of the property 'end'.
            
            # In Sphinx HTML output, cross-references are typically <a> tags with specific classes
            # or hrefs pointing to the referenced object.
            
            # Let's check if there's a link to mymod.Point in the HTML
            # The reference might look like: <a class="reference internal" href="#mymod.Point">Point</a>
            # or similar depending on Sphinx version and configuration.
            
            # A more robust check: look for any anchor/link containing "Point" near "end" property
            # Since we're checking if the bug is FIXED, we expect to see a proper cross-reference.
            
            # Check if "Point" appears as a cross-reference (linked) rather than just plain text
            # In the generated HTML for the property signature, if cross-referencing works,
            # the return type Point should be wrapped in an <a> tag linking to the Point class.
            
            # Look for pattern indicating a cross-reference to Point
            # Common patterns in Sphinx HTML:
            # <span class="pre">Point</span> inside <a> tag
            # or <code class="xref py py-class docutils literal notranslate"><span class="pre">Point</span></code>
            
            has_point_cross_ref = False
            
            # Check for various possible cross-reference patterns
            if 'href="#mymod.Point"' in html_content or 'href="index.html#mymod.Point"' in html_content:
                has_point_cross_ref = True
            elif '<a class="reference internal"' in html_content and 'Point' in html_content:
                # More detailed check: find if Point is within an anchor tag
                import re
                # Look for anchor tags containing Point
                anchor_pattern = r'<a[^>]*>.*?Point.*?</a>'
                if re.search(anchor_pattern, html_content, re.DOTALL | re.IGNORECASE):
                    has_point_cross_ref = True
                    
            # Also check for xref span patterns
            if '<code class="xref py py-class' in html_content and 'Point' in html_content:
                has_point_cross_ref = True
                
            assert has_point_cross_ref, "Cross-reference for Point type annotation in property 'end' was not found. The bug is still present."
            
            print("SUCCESS: Cross-references in property type annotations work correctly.")
            sys.exit(0)
            
        finally:
            # Remove srcdir from sys.path
            if srcdir in sys.path:
                sys.path.remove(srcdir)
                
    finally:
        # Cleanup temporary directory
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == '__main__':
    main()
