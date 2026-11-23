import sys
import os
import tempfile
import shutil
from pathlib import Path

def main():
    # Create a temporary directory for the test project
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        
        # Create the module with the issue's code
        module_code = '''
from typing import Optional

class Point:
    """
    A class representing a point.

    Attributes:
        x: Position X.
        y: Position Y.
    """
    x: int
    y: int


class Square:
    """A class representing a square figure."""
    #: Square's start position (top-left corner).
    start: Point
    #: Square width.
    width: int
    #: Square height.
    height: int

    @property
    def end(self) -> Point:
        """Square's end position (bottom-right corner)."""
        return Point(self.start.x + self.width, self.start.y + self.height)
'''
        (src_dir / "mymodule.py").write_text(module_code)

        # Create docs directory
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()
        
        # Create conf.py
        conf_py = '''
import sys
import os
sys.path.insert(0, os.path.abspath('../src'))

extensions = ['sphinx.ext.autodoc']
master_doc = 'index'
exclude_patterns = []
html_theme = 'basic'
'''
        (docs_dir / "conf.py").write_text(conf_py)
        
        # Create index.rst
        index_rst = '''
Test
====

.. automodule:: mymodule
   :members:
   :undoc-members:
'''
        (docs_dir / "index.rst").write_text(index_rst)

        # Build the documentation
        import sphinx.cmd.build
        
        build_dir = Path(tmpdir) / "_build"
        build_dir.mkdir()
        
        # Capture output to suppress it during testing
        from io import StringIO
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        
        try:
            result = sphinx.cmd.build.build_main([
                '-b', 'html',
                '-W',  # Treat warnings as errors
                str(docs_dir),
                str(build_dir)
            ])
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
        if result != 0:
            print("Sphinx build failed")
            sys.exit(1)
            
        # Check the generated HTML for cross-references
        html_file = build_dir / "index.html"
        if not html_file.exists():
            print("HTML file not generated")
            sys.exit(1)
            
        html_content = html_file.read_text()
        
        # The issue is that type annotations in property return types don't get cross-referenced.
        # We expect to see a link to the Point class in the documentation for Square.end
        # Look for a reference to mymodule.Point in the context of the 'end' property
        
        # In fixed Sphinx, the type annotation should be wrapped in a reference like:
        # <a class="reference internal" href="#mymodule.Point" title="mymodule.Point">Point</a>
        # or similar cross-reference markup
        
        # Let's check if there's a proper cross-reference to Point in the property documentation
        # The property 'end' has return type Point. We need to verify this is linked.
        
        # Find the section for Square.end
        # Look for patterns that indicate a cross-reference to Point
        # A proper cross-reference would contain something like 'href="#mymodule.Point"' or 'href="mymodule.html#mymodule.Point"'
        
        # Check if Point is referenced as a link in the HTML
        # In the fixed version, the type annotation should produce a cross-reference
        
        # Look for any <a> tag that references Point
        import re
        
        # Pattern to find links to Point class
        # Could be href="#mymodule.Point" or href="mymodule.html#mymodule.Point" etc.
        point_ref_pattern = r'href=["\'][^"\']*#mymodule\.Point["\']'
        
        if re.search(point_ref_pattern, html_content):
            # Found a proper cross-reference to Point
            print("Cross-reference to Point found - issue is fixed")
            sys.exit(0)
        else:
            # No cross-reference found - issue still exists
            print("No cross-reference to Point found - issue still exists")
            # Debug: print relevant parts of HTML
            # Find the end property section
            end_match = re.search(r'(.*?end.*?)(?=</dt>|<dt)', html_content, re.DOTALL | re.IGNORECASE)
            if end_match:
                print("Context around 'end':", end_match.group(1)[:500])
            sys.exit(1)

if __name__ == "__main__":
    main()
