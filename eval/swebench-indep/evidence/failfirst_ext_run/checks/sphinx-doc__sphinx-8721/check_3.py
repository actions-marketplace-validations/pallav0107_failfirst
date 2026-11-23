import os
import sys
import tempfile
import shutil
from pathlib import Path

def main():
    # Create a temporary directory for the Sphinx project
    with tempfile.TemporaryDirectory() as tmpdir:
        srcdir = Path(tmpdir) / "source"
        outdir_html = Path(tmpdir) / "build" / "html"
        outdir_epub = Path(tmpdir) / "build" / "epub"
        
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
Test Project
============

.. code-block:: python

   def hello():
       print("Hello World")
"""
        (srcdir / "index.rst").write_text(index_content)
        
        # Import Sphinx components
        from sphinx.application import Sphinx
        from sphinx.util.docutils import docutils_namespace
        
        # Build HTML first (often required or just part of the reproduction step `make html epub`)
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
            
        # Check if viewcode generated pages in the epub output.
        # The viewcode extension typically generates files like _modules/index.html 
        # or similar structure inside the build directory.
        # For epub, the output is an .epub file, but Sphinx also creates intermediate 
        # files in the output directory or the epub builder might create specific 
        # module pages if viewcode is active.
        
        # Let's look at what files are created in the epub build directory.
        # The issue states "viewcode creates pages for epub".
        # Usually, viewcode adds links to source code modules. If enabled for epub,
        # it would generate HTML files for modules. If disabled, it should not.
        
        # In Sphinx 3.x, the epub builder produces an .epub file and potentially 
        # supporting files. However, viewcode's behavior is controlled by 
        # `viewcode_enable_epub`. If False, it should not inject the viewcode logic 
        # that creates separate module pages or links.
        
        # A robust check is to see if the generated epub content contains references 
        # to viewcode-generated module pages, or if such pages exist in the interim 
        # build structure.
        
        # Since epub is a single file usually, we might need to inspect the contents 
        # or check if the builder skipped viewcode steps.
        # Alternatively, we can check if the 'viewcode' extension added any documents 
        # to the build environment specifically for epub.
        
        # Let's check if any _modules folder or similar was created in the epub output 
        # structure during the build process. The epub builder often keeps intermediate 
        # HTML files in the outdir before zipping them, or we can check the app.env 
        # to see if viewcode added documents.
        
        # Actually, a simpler way: check if the extension processed the viewcode 
        # directive/block for epub. If viewcode_enable_epub is False, the 
        # `html-collect-pages` or similar event should not add viewcode pages.
        
        # Let's look for _modules directory in the epub output path. 
        # Note: newer Sphinx versions might clean up, but intermediate files might remain 
        # or the epub file itself contains them.
        
        # Let's try to unzip the epub file if it exists and check for _modules.
        import zipfile
        
        epub_files = list(outdir_epub.glob("*.epub"))
        if not epub_files:
            # Maybe the output is just files? No, epub builder creates an epub file.
            # If no epub file, something went wrong with the build.
            raise AssertionError("EPUB file was not generated.")
            
        epub_path = epub_files[0]
        
        # Check contents of the epub file
        found_viewcode_pages = False
        with zipfile.ZipFile(epub_path, 'r') as z:
            names = z.namelist()
            for name in names:
                # Viewcode typically puts module sources in _modules/
                if '_modules/' in name:
                    found_viewcode_pages = True
                    break
                    
        # If viewcode_enable_epub is False, we should NOT find _modules pages
        assert not found_viewcode_pages, \
            "viewcode created pages for epub even though viewcode_enable_epub=False"

if __name__ == "__main__":
    main()
