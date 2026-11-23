import os
import sys
import tempfile
import shutil

def main():
    # Create a temporary directory for the test
    tmpdir = tempfile.mkdtemp()
    try:
        # Create the XML file to be included
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
        # The prepend string has 6 spaces of indentation to match the expected output
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

        # Configure Sphinx minimal build
        from sphinx.application import Sphinx
        from sphinx.util.docutils import docutils_namespace
        
        srcdir = tmpdir
        outdir = os.path.join(tmpdir, "_build", "html")
        doctreedir = os.path.join(tmpdir, "_build", "doctrees")
        confdir = tmpdir
        
        # Create a minimal conf.py
        conf_content = """
project = 'Test'
extensions = []
"""
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
                buildername='html',
                warningiserror=False,
                freshenv=True
            )
            app.build()

        # Read the generated HTML to check if the indentation is preserved
        html_path = os.path.join(outdir, "index.html")
        with open(html_path, "r") as f:
            html_content = f.read()

        # The expected behavior is that the prepend content retains its leading whitespace.
        # The prepend was "      <plugin>" (6 spaces).
        # In the HTML output, inside a <pre> or code block, we should see the indentation.
        # Sphinx typically renders literal blocks in <pre> tags.
        
        # Let's look for the specific pattern.
        # The included content starts with <groupId>...
        # The prepend is added before it.
        
        # We need to verify that the 6 spaces are present before <plugin> in the output.
        # Note: HTML might collapse whitespace unless it's in a <pre> block or using entities.
        # Sphinx uses Pygments for highlighting, which outputs HTML with spans.
        
        # Let's check if the raw text representation in the doctree preserves it, 
        # or check the HTML source for the spaces.
        
        # A more robust way is to check the doctree directly.
        doctree_path = os.path.join(doctreedir, "index.doctree")
        import pickle
        with open(doctree_path, "rb") as f:
            doctree = pickle.load(f)
            
        # Traverse the doctree to find the literal_block node
        from docutils import nodes
        
        def find_literal_blocks(node):
            blocks = []
            if isinstance(node, nodes.literal_block):
                blocks.append(node)
            for child in node.children:
                blocks.extend(find_literal_blocks(child))
            return blocks
            
        literal_blocks = find_literal_blocks(doctree)
        
        assert len(literal_blocks) > 0, "No literal block found in doctree"
        
        # There should be one literal block corresponding to our include
        block = literal_blocks[0]
        raw_text = block.astext()
        
        # The expected text should start with 6 spaces followed by <plugin>
        # Then a newline, then the included content.
        
        # Expected start: "      <plugin>\n        <groupId>..."
        # Note: The included content from pom.xml has its own indentation.
        # The line "<groupId>com.github.ekryd.sortpom</groupId>" in pom.xml is indented by 8 spaces.
        
        # Let's construct the expected beginning
        expected_start = "      <plugin>\n        <groupId>com.github.ekryd.sortpom</groupId>"
        
        # Check if the raw text starts with the expected indentation
        assert raw_text.startswith(expected_start), \
            f"Indentation not preserved. Expected start:\n{repr(expected_start)}\nActual start:\n{repr(raw_text[:len(expected_start)+50])}"

    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    main()
