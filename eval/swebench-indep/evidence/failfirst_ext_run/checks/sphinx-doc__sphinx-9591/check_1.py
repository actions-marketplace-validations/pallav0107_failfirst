import sys
import os
import tempfile
import shutil

def main():
    # Create a temporary directory for the test project
    tmpdir = tempfile.mkdtemp()
    try:
        # Create the Python module with the issue's code
        mod_dir = os.path.join(tmpdir, 'mymod')
        os.makedirs(mod_dir)
        
        with open(os.path.join(mod_dir, '__init__.py'), 'w') as f:
            f.write('')
            
        with open(os.path.join(mod_dir, 'example.py'), 'w') as f:
            f.write('''
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
''')

        # Create Sphinx configuration
        conf_content = '''
extensions = ['sphinx.ext.autodoc']
master_doc = 'index'
exclude_patterns = []
html_theme = 'basic'
'''
        with open(os.path.join(tmpdir, 'conf.py'), 'w') as f:
            f.write(conf_content)

        # Create index.rst
        index_content = '''
Test
====

.. automodule:: mymod.example
   :members:
'''
        with open(os.path.join(tmpdir, 'index.rst'), 'w') as f:
            f.write(index_content)

        # Add tmpdir to sys.path so sphinx can find the module
        sys.path.insert(0, tmpdir)

        # Import sphinx and build
        from sphinx.application import Sphinx
        from sphinx.util.docutils import docutils_namespace
        
        srcdir = tmpdir
        outdir = os.path.join(tmpdir, '_build', 'html')
        doctreedir = os.path.join(tmpdir, '_build', 'doctrees')
        confdir = tmpdir
        
        with docutils_namespace():
            app = Sphinx(
                srcdir=srcdir,
                confdir=confdir,
                outdir=outdir,
                doctreedir=doctreedir,
                buildername='html',
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app.build()

        # Check the generated HTML for cross-references in the property type annotation
        html_file = os.path.join(outdir, 'index.html')
        if not os.path.exists(html_file):
            print("HTML file not generated")
            sys.exit(1)
            
        with open(html_file, 'r') as f:
            html_content = f.read()
            
        # The issue is that cross-references don't work in property's type annotations.
        # If fixed, the type "Point" in the return type of the property "end" should be a link.
        # We look for a reference to mymod.example.Point in the context of the property 'end'.
        
        # In Sphinx HTML output, cross-references are typically <a> tags with href containing the reference.
        # We expect something like <a class="reference internal" href="#mymod.example.Point">Point</a>
        # or similar structure around the property's return type.
        
        # Let's check if there is an anchor/link for Point class near the property end documentation.
        # The property 'end' has return type Point. If cross-referencing works, "Point" should be linked.
        
        # Simple check: look for a link to the Point class definition in the HTML
        # The Point class will have an id like "mymod.example.Point"
        # The reference should be an <a> tag pointing to it.
        
        # Check if there's a reference to mymod.example.Point
        if 'href="#mymod.example.Point"' in html_content or 'href=\'#mymod.example.Point\'' in html_content:
            # There is at least one reference to Point. Now we need to verify it's in the property context.
            # This is a bit tricky with simple string matching. 
            # Let's check if the property 'end' section contains a link to Point.
            
            # Find the section for property 'end'
            # In basic theme, properties are documented. Let's look for the property name and then check for a link nearby.
            
            # A more robust way: parse the doctree or check specific patterns.
            # For simplicity, let's assume if there's ANY link to Point, and the property is documented, 
            # we need to ensure the type annotation in the property IS linked.
            
            # Let's look for the pattern where 'end' property is described and 'Point' is linked.
            # The output usually looks like:
            # <dt class="property">
            # <em class="property"><span class="k"><span class="pre">property</span></span><span class="w"> </span></em><code class="sig-name descname"><span class="pre">end</span></code><span class="sig-paren">(</span><span class="sig-paren">)</span> <span class="sig-return"><span class="sig-return-icon">&#x2192;</span> <span class="sig-return-typehint"><a class="reference internal" href="#mymod.example.Point" title="mymod.example.Point"><code class="xref py py-class docutils literal notranslate"><span class="pre">Point</span></code></a></span></span>
            
            # Check for the sig-return-typehint containing a reference to Point
            if 'sig-return-typehint' in html_content:
                # Extract the part after sig-return-typehint and check if it contains a link to Point
                import re
                # Look for the pattern: sig-return-typehint ... <a ... href="#mymod.example.Point" ... >Point</a>
                pattern = r'sig-return-typehint.*?href=["\']#mymod\.example\.Point["\'].*?>Point</a>'
                if re.search(pattern, html_content, re.DOTALL):
                    print("Cross-reference found in property return type.")
                    sys.exit(0)
                else:
                    # Maybe the format is different, let's check more broadly
                    # Check if there is any <a> tag with href to Point inside a property context
                    # Find all occurrences of property end
                    pass
                    
            # Fallback: just check if there is a link to Point anywhere. 
            # But the issue specifically says property type annotations don't get cross-referenced.
            # So if we find a link to Point, it might be from the attribute 'start: Point' which DOES work.
            # We need to distinguish between the attribute and the property return type.
            
            # Let's check the doctree instead for more precision
            doctree_file = os.path.join(doctreedir, 'index.doctree')
            if os.path.exists(doctree_file):
                import pickle
                with open(doctree_file, 'rb') as f:
                    doctree = pickle.load(f)
                
                # Traverse the doctree to find the property 'end' and check its return type annotation
                from docutils import nodes
                
                def find_property_end(node):
                    """Find the node for property 'end' and check if return type has a reference."""
                    if isinstance(node, nodes.desc_signature):
                        # Check if this is the signature for 'end'
                        for child in node.traverse(nodes.desc_name):
                            if child.astext() == 'end':
                                # Found the signature for 'end'
                                # Look for sig_return_type or similar
                                for ret_node in node.traverse(nodes.reference):
                                    if ret_node.get('refid') == 'mymod.example.Point' or ret_node.get('refuri') == '#mymod.example.Point':
                                        return True
                    return False
                
                # Actually, let's look for desc_signature containing 'end' and then check for references to Point
                found_linked_property = False
                for sig in doctree.traverse(nodes.desc_signature):
                    # Check if this signature belongs to 'end'
                    names = [n.astext() for n in sig.traverse(nodes.desc_name)]
                    if 'end' in names:
                        # Check if there's a reference to Point in this signature
                        for ref in sig.traverse(nodes.reference):
                            refid = ref.get('refid', '')
                            refuri = ref.get('refuri', '')
                            if 'mymod.example.Point' in refid or 'mymod.example.Point' in refuri:
                                found_linked_property = True
                                break
                
                if found_linked_property:
                    print("Property return type is correctly cross-referenced.")
                    sys.exit(0)
                else:
                    print("Property return type is NOT cross-referenced.")
                    assert False, "Cross-reference in property type annotation is missing"
            else:
                # If no doctree, rely on HTML check
                # Count how many times Point is linked. 
                # Attribute 'start' should create one link. Property 'end' should create another if fixed.
                link_count = html_content.count('href="#mymod.example.Point"') + html_content.count("href='#mymod.example.Point'")
                # If only 1 link, it's likely just the attribute. If 2+, property is also linked.
                # But this is fragile. Let's use the doctree approach as primary.
                if link_count >= 2:
                     print("Multiple references to Point found, likely including property.")
                     sys.exit(0)
                else:
                     print("Only one or no reference to Point found.")
                     assert False, "Cross-reference in property type annotation is missing"
        else:
            print("No reference to Point class found at all.")
            assert False, "Cross-reference to Point class is missing entirely"

    finally:
        # Cleanup
        if tmpdir in sys.path:
            sys.path.remove(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == '__main__':
    main()
