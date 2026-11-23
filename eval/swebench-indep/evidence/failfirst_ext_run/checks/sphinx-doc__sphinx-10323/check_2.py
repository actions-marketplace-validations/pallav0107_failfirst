import os
import sys
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
        # Note: The issue shows prepend with leading spaces: "       </plugin>"
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

        os.makedirs(outdir, exist_ok=True)
        
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

        # Read the generated HTML to check if indentation is preserved
        html_path = os.path.join(outdir, "index.html")
        with open(html_path, "r") as f:
            html_content = f.read()

        # The issue states that leading whitespace in prepend is removed.
        # Expected behavior: leading whitespace should be preserved.
        # The prepend was "       <plugin>" (7 spaces before <plugin>)
        # If fixed, the HTML should contain the indented <plugin> tag.
        
        # In HTML output, literal blocks are usually inside <pre> tags.
        # Whitespace might be represented as spaces or entities depending on settings.
        # Let's check if the specific pattern of indentation exists.
        
        # The included content starts with:
        #       <plugin>
        #         <groupId>com.github.ekryd.sortpom</groupId>
        # ...
        #       </plugin>
        
        # If the bug exists, the prepend line will be "<plugin>" without leading spaces.
        # If fixed, it should be "       <plugin>" (or equivalent whitespace).
        
        # Let's look for the prepend content in the HTML.
        # Sphinx typically outputs literal content in <div class="highlight"> or similar.
        
        # We need to verify that the leading spaces from :prepend: are preserved.
        # The prepend value was "       <plugin>" (7 spaces).
        
        # Check if the HTML contains the indented plugin tag.
        # Since it's XML/HTML, we look for the text content.
        
        # A robust check: look for the sequence of spaces followed by <plugin>
        # In the raw HTML source, spaces are usually preserved in <pre> blocks.
        
        # Let's extract the relevant part.
        # The bug is that spaces are stripped. So if fixed, spaces should be there.
        
        # Search for "       <plugin>" in the HTML content
        # Note: HTML might encode spaces as &nbsp; or just keep them in pre tags.
        # Standard Sphinx HTML builder keeps spaces in <pre> tags.
        
        # Let's check if the string with leading spaces exists.
        prepend_with_spaces = "       <plugin>"
        
        # Also check if the unindented version exists (which would indicate the bug)
        prepend_without_spaces = "<plugin>"
        
        # We need to be careful: the included body also has <plugin> tags potentially.
        # But the prepend is at the very beginning of the literal block.
        
        # Let's find the literal block in the HTML.
        # It should be inside a <pre> tag.
        
        import re
        
        # Find all <pre> blocks
        pre_blocks = re.findall(r'<pre[^>]*>(.*?)</pre>', html_content, re.DOTALL)
        
        found_correct_indentation = False
        for block in pre_blocks:
            # Decode HTML entities if any
            import html
            decoded_block = html.unescape(block)
            
            # Check if the block starts with the indented prepend
            # The first line should be "       <plugin>"
            lines = decoded_block.split('\n')
            if lines:
                first_line = lines[0]
                # Strip trailing whitespace but keep leading
                first_line_stripped_trailing = first_line.rstrip()
                
                if first_line_stripped_trailing == prepend_with_spaces:
                    found_correct_indentation = True
                    break
        
        assert found_correct_indentation, \
            f"Leading whitespace in :prepend: was not preserved. " \
            f"Expected first line to be '{prepend_with_spaces}'. " \
            f"HTML content snippet: {html_content[:2000]}"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    main()
