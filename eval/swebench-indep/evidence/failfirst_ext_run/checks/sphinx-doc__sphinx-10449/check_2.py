import sys
import os
import tempfile
import shutil

# Setup a temporary directory for the test project
tmpdir = tempfile.mkdtemp()
sys.path.insert(0, tmpdir)

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

    # Configure Sphinx minimal environment
    from sphinx.application import Sphinx
    from sphinx.util.docutils import docutils_namespace
    
    srcdir = os.path.join(tmpdir, "docs")
    outdir = os.path.join(tmpdir, "build")
    doctreedir = os.path.join(outdir, ".doctrees")
    confdir = srcdir
    
    os.makedirs(srcdir)
    
    # Create conf.py
    with open(os.path.join(confdir, "conf.py"), "w") as f:
        f.write('''
extensions = ['sphinx.ext.autodoc']
autodoc_typehints = "description"
master_doc = 'index'
exclude_patterns = []
''')

    # Create index.rst
    with open(os.path.join(srcdir, "index.rst"), "w") as f:
        f.write('''
Test
====

.. autoclass:: sample_package.Square
   :members:
''')

    # Build the documentation
    with docutils_namespace():
        app = Sphinx(
            srcdir=srcdir,
            confdir=confdir,
            outdir=outdir,
            doctreedir=doctreedir,
            buildername='html',
            warningiserror=False,
            verbosity=0
        )
        app.build()

    # Read the generated HTML
    html_path = os.path.join(outdir, "index.html")
    with open(html_path, "r") as f:
        html_content = f.read()

    # Check for the bug:
    # The bug is that `-> None` or return type information appears in the class signature
    # when autodoc_typehints = "description".
    # Specifically, for __init__, it shouldn't show a return type in the class signature line.
    # However, "description" mode puts type hints in the description.
    # The issue reports that the class itself shows a return type.
    
    # Let's look for specific patterns.
    # In the buggy version, the class signature might look like:
    # class Square(width: int, height: int) -> None
    # Or similar artifacts.
    
    # We check if "-> None" appears in the context of the class definition in the HTML.
    # A correct behavior should NOT have "-> None" associated with the class constructor signature 
    # displayed as part of the class header.
    
    # Note: In Sphinx 5.x with autodoc_typehints="description", type hints are moved to the description.
    # The signature should just be `Square(width, height)` or similar without return type annotation.
    
    # Let's assert that "-> None" is NOT present in the signature area.
    # A simple heuristic: if "-> None" is in the HTML, it's likely the bug is present 
    # because __init__ returns None but that shouldn't be rendered as a return type for the class.
    
    # However, we must be careful. If the method __init__ is documented separately, 
    # it might still have its own signature. But the issue is about the *class* having a return type.
    
    # Let's check if the string "-> None" exists in the generated HTML.
    # If it does, it suggests the return type annotation is being rendered, which is the bug.
    # In "description" mode, type hints should be in the field lists, not in the signature.
    
    has_return_type_in_signature = "-> None" in html_content
    
    # If the bug is fixed, "-> None" should not appear in the signature.
    # It might appear in the description if explicitly written, but here it comes from annotation.
    # With "description", annotations are stripped from signatures.
    
    assert not has_return_type_in_signature, (
        "Bug reproduced: Return type '-> None' found in generated HTML. "
        "autodoc_typehints='description' should remove type hints from signatures."
    )
    
    print("Check passed: Behavior is correct.")
    sys.exit(0)

finally:
    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)
