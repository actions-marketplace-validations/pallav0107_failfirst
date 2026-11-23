import os
import sys
import tempfile
import shutil
from pathlib import Path

def main():
    # Create a temporary directory for the test project
    with tempfile.TemporaryDirectory() as tmpdir:
        srcdir = Path(tmpdir) / "source"
        outdir_html = Path(tmpdir) / "build_html"
        outdir_epub = Path(tmpdir) / "build_epub"
        
        srcdir.mkdir()
        
        # Create conf.py
        conf_content = """
project = 'TestProject'
extensions = ['sphinx.ext.viewcode']
viewcode_enable_epub = False
"""
        (srcdir / "conf.py").write_text(conf_content)
        
        # Create index.rst with some code to trigger viewcode
        index_content = """
Test
====

.. code-block:: python

   def hello():
       pass
"""
        (srcdir / "index.rst").write_text(index_content)
        
        # Create a simple Python module to ensure viewcode has something to link to
        # Viewcode typically links to source files of imported modules or local modules.
        # To make it robust, let's create a small module in the path.
        mod_dir = srcdir / "_static" # Not ideal for imports, let's just use a dummy module approach
        # Actually, viewcode works by analyzing the doctree and linking to source files.
        # If we don't have real python files, it might not generate pages.
        # Let's create a dummy python file in the source directory and import it in conf.py or index?
        # No, viewcode usually picks up modules that are documented or imported.
        
        # Let's refine the setup to ensure viewcode actually tries to do something.
        # We will create a dummy module 'dummy_mod' in the srcdir and add srcdir to sys.path in conf.py
        
        dummy_py_content = """
def dummy_func():
    '''A dummy function'''
    pass
"""
        (srcdir / "dummy_mod.py").write_text(dummy_py_content)
        
        # Update conf.py to include the path and automodule or just import
        conf_content_updated = """
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

project = 'TestProject'
extensions = ['sphinx.ext.viewcode', 'sphinx.ext.autodoc']
viewcode_enable_epub = False
"""
        (srcdir / "conf.py").write_text(conf_content_updated)
        
        # Update index.rst to document the module
        index_content_updated = """
Test
====

.. automodule:: dummy_mod
   :members:
"""
        (srcdir / "index.rst").write_text(index_content_updated)

        # Import Sphinx components
        from sphinx.application import Sphinx
        from sphinx.util.docutils import docutils_namespace
        
        # Build HTML first (to ensure normal operation)
        with docutils_namespace():
            app_html = Sphinx(
                srcdir=str(srcdir),
                confdir=str(srcdir),
                outdir=str(outdir_html),
                doctreedir=str(outdir_html / ".doctrees"),
                buildername='html',
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app_html.build()
            
        # Build EPUB
        with docutils_namespace():
            app_epub = Sphinx(
                srcdir=str(srcdir),
                confdir=str(srcdir),
                outdir=str(outdir_epub),
                doctreedir=str(outdir_epub / ".doctrees"),
                buildername='epub',
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app_epub.build()
            
        # Check if viewcode generated pages in the epub build
        # Viewcode typically generates files like _modules/index.html or similar in the output
        # In HTML build, it creates _modules/ directory.
        # In EPUB build, if viewcode_enable_epub is False, it should NOT create these pages.
        
        # Let's look for any html files inside the epub output that look like viewcode output.
        # The epub builder creates an .epub file, but it also creates intermediate files in outdir?
        # Actually, the epub builder creates the epub archive. But before that, it processes files.
        # However, the issue says "viewcode creates pages for epub".
        # Let's check the contents of the generated epub file or the intermediate structure.
        
        # The epub builder usually writes to a single .epub file.
        # But internally, it might generate HTML fragments.
        # Let's check if there are any files related to viewcode in the outdir.
        # Wait, the epub builder output is primarily the .epub file.
        # Let's inspect the epub file content.
        
        import zipfile
        
        epub_files = list(outdir_epub.glob("*.epub"))
        assert len(epub_files) >= 1, "No epub file generated"
        
        epub_path = epub_files[0]
        
        # Check contents of the epub file for viewcode-related files
        # Viewcode usually puts source code listings in _modules/ or similar
        found_viewcode_pages = False
        
        with zipfile.ZipFile(epub_path, 'r') as z:
            names = z.namelist()
            for name in names:
                # Viewcode pages often contain 'viewcode' or are in _modules directory
                # Or they might be named after the module, e.g., dummy_mod.html
                # Let's look for _modules/ which is standard for viewcode
                if '_modules/' in name or 'viewcode' in name.lower():
                    # Exclude CSS/JS if they are just assets, but viewcode creates HTML pages
                    if name.endswith('.html'):
                        found_viewcode_pages = True
                        print(f"Found unexpected viewcode page in epub: {name}")
                        break
                        
        # If viewcode_enable_epub is False, we should NOT find viewcode pages
        # The issue states that pages ARE created even when False.
        # So if found_viewcode_pages is True, the bug exists (exit non-zero).
        # If found_viewcode_pages is False, the bug is fixed (exit 0).
        
        assert not found_viewcode_pages, "viewcode created pages in epub despite viewcode_enable_epub=False"

if __name__ == '__main__':
    main()
