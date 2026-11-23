import sys
import os
import tempfile
import shutil

def main():
    # Create a temporary directory for the test
    tmpdir = tempfile.mkdtemp()
    try:
        # Create the XML file
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<project>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.8.0</version>
        <configuration>
          <source>1.8</source>
          <target>1.8</target>
          <debug>true</debug>
          <encoding>UTF-8</encoding>
        </configuration>
      </plugin>
      <plugin>
        <groupId>com.github.ekryd.sortpom</groupId>
        <artifactId>sortpom-maven-plugin</artifactId>
        <version>2.15.0</version>
        <configuration>
          <verifyFailOn>strict</verifyFailOn>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
"""
        xml_path = os.path.join(tmpdir, "pom.xml")
        with open(xml_path, "w") as f:
            f.write(xml_content)

        # Create the RST file
        rst_content = """Test
====

.. literalinclude:: pom.xml
   :language: xml
   :prepend:       <plugin>
   :start-at: <groupId>com.github.ekryd.sortpom</groupId>
   :end-at: </plugin>
"""
        rst_path = os.path.join(tmpdir, "index.rst")
        with open(rst_path, "w") as f:
            f.write(rst_content)

        # Configure Sphinx minimal app
        from sphinx.application import Sphinx
        from sphinx.util.docutils import docutils_namespace
        
        srcdir = tmpdir
        outdir = os.path.join(tmpdir, "_build", "html")
        doctreedir = os.path.join(tmpdir, "_build", "doctrees")
        confdir = tmpdir
        
        # Create a minimal conf.py
        conf_content = "extensions = []\n"
        conf_path = os.path.join(tmpdir, "conf.py")
        with open(conf_path, "w") as f:
            f.write(conf_content)

        # Build the documentation
        with docutils_namespace():
            app = Sphinx(
                srcdir=srcdir,
                confdir=confdir,
                outdir=outdir,
                doctreedir=doctreedir,
                buildername="html",
                freshenv=True,
                warningiserror=False,
                verbosity=0
            )
            app.build()

        # Read the generated HTML to check if the prepend whitespace is preserved
        html_path = os.path.join(outdir, "index.html")
        with open(html_path, "r") as f:
            html_content = f.read()

        # The issue states that leading whitespace in prepend is removed.
        # Expected behavior: leading whitespace should be preserved.
        # The prepend is "       <plugin>" (7 spaces + <plugin>)
        # We need to check if the output contains the indented plugin tag.
        
        # In the HTML output, the code block will be inside <pre> or similar.
        # The literalinclude content starts with <groupId>...
        # With prepend, it should start with "       <plugin>\n        <groupId>..."
        
        # Let's look for the specific pattern in the HTML.
        # The HTML entity for space is &nbsp; or just spaces depending on rendering.
        # In raw HTML source, spaces are usually preserved inside <pre> tags.
        
        # Check if the 7 spaces before <plugin> are present in the HTML source
        # The prepend string is "       <plugin>" (7 spaces)
        
        # Since the HTML might encode spaces differently, let's check the doctree instead
        # which is more reliable for checking the actual text content.
        
        doctree_path = os.path.join(doctreedir, "index.doctree")
        from sphinx.serializing_pickle import load
        with open(doctree_path, "rb") as f:
            doctree = load(f)
        
        # Traverse the doctree to find the literal_block node
        def find_literal_blocks(node):
            blocks = []
            if hasattr(node, 'tagname') and node.tagname == 'literal_block':
                blocks.append(node)
            if hasattr(node, 'children'):
                for child in node.children:
                    blocks.extend(find_literal_blocks(child))
            return blocks
        
        literal_blocks = find_literal_blocks(doctree)
        
        assert len(literal_blocks) > 0, "No literal_block found in doctree"
        
        # Get the first literal block content
        block = literal_blocks[0]
        # The content is stored in the astext() method or as children
        block_text = block.astext()
        
        print("Block text representation:")
        print(repr(block_text))
        
        # The expected text should start with 7 spaces followed by <plugin>
        # Then a newline, then the included content
        
        # Check if the prepend whitespace is preserved
        # The prepend was "       <plugin>" (7 spaces)
        expected_start = "       <plugin>"
        
        # The block text should contain this exact string at the beginning
        assert block_text.startswith(expected_start), \
            f"Prepend whitespace not preserved. Expected to start with {repr(expected_start)}, but got {repr(block_text[:50])}"
        
        print("SUCCESS: Prepend whitespace is correctly preserved.")
        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
