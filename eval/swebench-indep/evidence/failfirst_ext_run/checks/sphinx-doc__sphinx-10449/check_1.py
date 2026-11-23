import sys
import os
import tempfile
import shutil

def main():
    # Create a temporary directory for the test package and build output
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup the sample package
        pkg_dir = os.path.join(tmpdir, 'sample_package')
        os.makedirs(pkg_dir)
        
        with open(os.path.join(pkg_dir, '__init__.py'), 'w') as f:
            f.write('''
class Square:
    """A class representing a square figure."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
''')

        # Setup Sphinx docs configuration
        docs_dir = os.path.join(tmpdir, 'docs')
        os.makedirs(docs_dir)
        build_dir = os.path.join(docs_dir, '_build')
        
        # Add the parent of sample_package to sys.path so it can be imported
        sys.path.insert(0, tmpdir)
        
        conf_content = '''
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'Test'
extensions = ['sphinx.ext.autodoc']
autodoc_typehints = "description"
html_theme = 'basic'
'''
        with open(os.path.join(docs_dir, 'conf.py'), 'w') as f:
            f.write(conf_content)
            
        index_rst = '''
Test
====

.. autoclass:: sample_package.Square
   :members:
'''
        with open(os.path.join(docs_dir, 'index.rst'), 'w') as f:
            f.write(index_rst)

        # Run Sphinx build
        from sphinx.application import Sphinx
        
        try:
            app = Sphinx(
                srcdir=docs_dir,
                confdir=docs_dir,
                outdir=os.path.join(build_dir, 'html'),
                doctreedir=os.path.join(build_dir, 'doctrees'),
                buildername='html',
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app.build()
        except Exception as e:
            print(f"Sphinx build failed: {e}", file=sys.stderr)
            sys.exit(1)

        # Read the generated HTML
        html_file = os.path.join(build_dir, 'html', 'index.html')
        if not os.path.exists(html_file):
            print("Generated HTML file not found", file=sys.stderr)
            sys.exit(1)
            
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # The bug is that the return type (None) of __init__ appears in the class signature
        # or near the class definition when autodoc_typehints = "description".
        # Specifically, it might look like "-> None" in the class signature area.
        
        # We check if "-> None" appears in the context of the class signature.
        # In the buggy version, the class signature might look like:
        # class Square(width: int, height: int) -> None
        
        # Let's look for the specific pattern that indicates the bug.
        # The issue states that autoclass puts a return type for the class.
        # This usually manifests in the signature line of the class.
        
        # We will parse the docutils doctree or just check the HTML for the anomaly.
        # Checking HTML is fragile but direct. A more robust way is to check the 
        # rendered signature in the doctree if we had access to it, but here we have HTML.
        
        # In the fixed version, the class signature should NOT contain "-> None".
        # The __init__ method's return type should be handled separately or ignored for the class signature.
        
        # Let's look for the class signature in the HTML.
        # Typically: <em class="property">class </em><code class="sig-name descname">Square</code><span class="sig-paren">(</span><em class="sig-param"><span class="n">width</span><span class="p">:</span> <span class="n">int</span></em>, <em class="sig-param"><span class="n">height</span><span class="p">:</span> <span class="n">int</span></em><span class="sig-paren">)</span>
        # Buggy version might have: ...<span class="sig-paren">)</span> <span class="sig-return"><span class="sig-return-icon">&#x2192;</span> <span class="sig-return-typehint">None</span></span>
        
        # Check if "-> None" or the HTML equivalent exists in the class signature block.
        # Since "description" mode moves typehints to description, they shouldn't be in signature.
        
        # Simple check: if "-> None" is present in the HTML, it's likely the bug persists 
        # because __init__ returns None and this shouldn't appear in the class signature.
        # However, we must ensure we are not catching legitimate return types elsewhere.
        # Given the minimal example, only __init__ has a return type annotation.
        
        # A more precise check: look for the class signature specifically.
        # The bug report shows that the class itself gets the return type of __init__.
        
        if '-> None' in html_content or '&#x2192;' in html_content:
             # Verify it's associated with the class Square signature, not just any text.
             # In the buggy case, the class signature line contains the return type.
             
             # Let's refine: The bug is that the CLASS signature includes the return type.
             # We can check if the string "Square" is followed by parameters and then "-> None" 
             # before the next tag or section.
             
             # For simplicity and robustness against HTML structure changes, 
             # we assert that the class signature does NOT contain the return type indicator.
             
             # If the bug is present, the HTML will contain the arrow and None near Square.
             pass
             
        # Assert that the bug is FIXED.
        # The bug is fixed if the return type is NOT in the class signature.
        # Since autodoc_typehints="description", typehints should be in the description, 
        # not the signature. So "-> None" should not appear in the signature part.
        
        # Let's check if the specific buggy pattern exists.
        # Pattern: class Square(...) -> None
        
        # We'll use a simple heuristic: if the HTML contains "-> None" it is likely the bug
        # because there are no other functions with return types in this minimal example.
        # Wait, if the fix moves it to description, it might still be in the HTML but in the 
        # description paragraph, not the signature.
        
        # The issue title says "causes autoclass to put a return type". This implies it appears 
        # where it shouldn't, i.e., in the class signature.
        
        # Let's look at the generated doctree or object inventory if possible? No, HTML only.
        
        # Better approach: Check the signature span specifically.
        # In Sphinx HTML, signatures are in <dt> tags with class "sig".
        
        import re
        
        # Find all signature blocks
        sig_pattern = r'<dt[^>]*class="[^"]*sig[^"]*"[^>]*>.*?</dt>'
        sigs = re.findall(sig_pattern, html_content, re.DOTALL)
        
        class_sig_found = False
        bug_present = False
        
        for sig in sigs:
            if 'Square' in sig:
                class_sig_found = True
                # Check if this signature contains a return type indicator
                if '->' in sig or '&#x2192;' in sig:
                    bug_present = True
                    
        if not class_sig_found:
            print("Could not find Square class signature in HTML", file=sys.stderr)
            sys.exit(1)
            
        # If bug is present, exit with non-zero (AssertionError)
        # If bug is fixed, exit with 0
        assert not bug_present, "Bug is still present: Class signature contains return type"

if __name__ == '__main__':
    main()
