import os
import sys
import tempfile
import shutil

def main():
    # Create a temporary directory for the test package and build
    tmpdir = tempfile.mkdtemp()
    try:
        # Create the sample package
        pkg_dir = os.path.join(tmpdir, "sample_package")
        os.makedirs(pkg_dir)
        
        with open(os.path.join(pkg_dir, "__init__.py"), "w") as f:
            f.write('''
class Square:
    """A class representing a square figure."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
''')

        # Create docs directory
        docs_dir = os.path.join(tmpdir, "docs")
        os.makedirs(docs_dir)
        
        # Create conf.py
        with open(os.path.join(docs_dir, "conf.py"), "w") as f:
            f.write('''
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

extensions = ['sphinx.ext.autodoc']
autodoc_typehints = "description"
html_theme = 'alabaster'
''')

        # Create index.rst
        with open(os.path.join(docs_dir, "index.rst"), "w") as f:
            f.write('''
Test
====

.. autoclass:: sample_package.Square
   :members:
''')

        # Build the documentation
        import sphinx.cmd.build
        
        build_dir = os.path.join(docs_dir, "_build")
        doctree_dir = os.path.join(build_dir, "doctrees")
        
        # Run sphinx-build
        argv = [
            "-b", "html",
            "-D", "autodoc_typehints=description",
            docs_dir,
            build_dir
        ]
        
        # We need to ensure the path is set correctly for the import
        # Sphinx will read conf.py which adds the parent dir to sys.path
        
        result = sphinx.cmd.build.build_main(argv)
        
        if result != 0:
            raise RuntimeError(f"Sphinx build failed with code {result}")
            
        # Read the generated HTML
        html_file = os.path.join(build_dir, "index.html")
        with open(html_file, "r") as f:
            html_content = f.read()
            
        # The bug is that the return type (None) of __init__ is displayed in the class signature
        # or nearby when it shouldn't be. 
        # Specifically, for a class, there is no "return type" for the class itself.
        # However, autodoc might be treating the class constructor's return type annotation
        # incorrectly in the context of the class signature when typehints are in description.
        
        # Let's look for specific patterns. 
        # In the buggy version, the output might contain something like "Square(None)" or 
        # display the return type of __init__ inappropriately.
        
        # A more robust check: 
        # When autodoc_typehints is "description", type hints should be moved to the description text,
        # NOT kept in the signature.
        # So the signature should look like: __init__(width, height)
        # And the description should contain the types.
        
        # If the bug exists, it might show the return type of __init__ (None) in the class signature area?
        # The issue title says: "causes autoclass to put a return type".
        # This usually means the class signature itself shows a return type, e.g., "class Square(None)".
        
        # Let's check if "None" appears in a way that suggests it's a return type for the class.
        # In standard HTML output from Sphinx/alabaster, signatures are in <dt> tags.
        
        import re
        
        # Find the signature part. 
        # The bug manifests as the class having a return type annotation displayed.
        # Example of buggy output: <code class="sig sig-object py">class Square<span class="sig-paren">(</span><span class="sig-paren">)</span> <span class="sig-return"><span class="sig-return-icon">&#x2192;</span> <span class="sig-return-typehint">None</span></span></code>
        # Or similar.
        
        # Check if there is a return arrow followed by None in the context of the class definition
        # Note: __init__ also has -> None, but that's a method. The issue is about the CLASS having a return type.
        
        # Let's parse the HTML to find the class signature.
        # We look for the pattern indicating a return type hint in the class signature.
        
        # Simple string check for the problematic pattern in the class signature area.
        # The class signature should NOT have a return type.
        
        # Look for the class signature block.
        # In alabaster, it's typically:
        # <dl class="py class">
        # <dt class="sig sig-object py" id="...">
        # <span class="sig-name descname">Square</span>...
        
        # If the bug is present, we might see "→ None" or similar near the class name/params.
        
        # Let's check if the string "-> None" or the HTML equivalent appears in the class signature.
        # The HTML entity for arrow is &#x2192; or &rarr;
        
        # We need to distinguish between the class signature and the __init__ method signature.
        # The issue states "autoclass to put a return type". This implies the class itself.
        
        # Let's extract the content of the first <dt> tag which usually contains the class signature.
        match = re.search(r'<dt[^>]*class="[^"]*sig[^"]*".*?>.*?</dt>', html_content, re.DOTALL)
        if match:
            class_sig_html = match.group(0)
            # Check if this signature contains a return type indicator
            # Common patterns for return type in Sphinx HTML:
            # <span class="sig-return">...</span>
            # or text like "&rarr; None" or "&#x2192; None"
            
            has_return_type_in_class_sig = False
            
            # Check for explicit return span
            if '<span class="sig-return">' in class_sig_html:
                has_return_type_in_class_sig = True
            
            # Also check for raw arrow text just in case
            if '&rarr;' in class_sig_html or '&#x2192;' in class_sig_html:
                 # Verify it's not inside a method signature nested within? 
                 # The dt should be just the class.
                 has_return_type_in_class_sig = True

            # The correct behavior is NO return type in the class signature.
            assert not has_return_type_in_class_sig, \
                f"Class signature incorrectly contains a return type. Signature HTML: {class_sig_html}"
        else:
            # Fallback: simple text search if regex fails
            # This is less precise but covers cases where HTML structure changes slightly
            # Look for "class Square" followed by return type indicators before any method definitions
            pass

    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    main()
