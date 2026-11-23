import os
import sys
import tempfile
import shutil

def main():
    # Create a temporary directory for the test project
    tmpdir = tempfile.mkdtemp()
    try:
        # Create minimal Sphinx project structure
        srcdir = os.path.join(tmpdir, 'source')
        outdir_html = os.path.join(tmpdir, 'build', 'html')
        outdir_epub = os.path.join(tmpdir, 'build', 'epub')
        
        os.makedirs(srcdir)
        
        # Create conf.py
        conf_content = """
project = 'Test'
extensions = ['sphinx.ext.viewcode']
viewcode_enable_epub = False
"""
        with open(os.path.join(srcdir, 'conf.py'), 'w') as f:
            f.write(conf_content)
            
        # Create index.rst with some code to trigger viewcode
        index_content = """
Test
====

.. code-block:: python

   def hello():
       print("world")
"""
        with open(os.path.join(srcdir, 'index.rst'), 'w') as f:
            f.write(index_content)
            
        # Import sphinx components
        from sphinx.application import Sphinx
        from sphinx.util.docutils import docutils_namespace
        
        # Build HTML first (to ensure viewcode generates links in HTML)
        with docutils_namespace():
            app_html = Sphinx(
                srcdir=srcdir,
                confdir=srcdir,
                outdir=outdir_html,
                doctreedir=os.path.join(tmpdir, 'doctrees'),
                buildername='html',
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app_html.build()
            
        # Build EPUB
        with docutils_namespace():
            app_epub = Sphinx(
                srcdir=srcdir,
                confdir=srcdir,
                outdir=outdir_epub,
                doctreedir=os.path.join(tmpdir, 'doctrees'),
                buildername='epub',
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app_epub.build()
            
        # Check if viewcode created pages in epub output
        # Viewcode typically creates files like _modules/index.html or similar in the output
        # In epub, the output is usually a single .epub file, but intermediate files might exist
        # Let's check the epub builder's output structure
        
        # The epub builder creates an .epub file. We need to check if viewcode added extra pages.
        # However, viewcode for epub works by adding entries to the epub manifest/content.
        # A better check: look at the generated epub content or the intermediate doctrees/outputs.
        
        # Actually, let's look at what files are in the epub output directory.
        # The epub builder outputs a .epub file. But it also creates temporary structures.
        # Let's inspect the app.env to see if viewcode added documents.
        
        # Alternative approach: Check if the epub build produced any module documentation pages
        # that shouldn't be there. 
        
        # Let's check the master_doc and related docs in the epub environment.
        # Viewcode adds documents to the env.found_docs.
        
        # Re-build epub and check env.found_docs for viewcode-generated docs
        with docutils_namespace():
            app_check = Sphinx(
                srcdir=srcdir,
                confdir=srcdir,
                outdir=outdir_epub,
                doctreedir=os.path.join(tmpdir, 'doctrees'),
                buildername='epub',
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app_check.build()
            
            # Check if any viewcode-related documents were added
            # Viewcode typically creates documents with names like '_modules/...'
            found_docs = app_check.env.found_docs
            
            viewcode_docs = [doc for doc in found_docs if doc.startswith('_modules/') or '/_modules/' in doc]
            
            # If viewcode_enable_epub is False, there should be no viewcode docs in epub
            assert len(viewcode_docs) == 0, f"Viewcode created pages in epub despite viewcode_enable_epub=False: {viewcode_docs}"
            
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        
    sys.exit(0)

if __name__ == '__main__':
    main()
