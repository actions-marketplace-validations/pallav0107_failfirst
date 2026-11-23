import sys
import tempfile
import os

def main():
    # Create a minimal Python file to lint
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("foo = 1\n")
        temp_py = f.name

    # Create a pylintrc configuration file that triggers the bug
    # The regex "(foo{1,3})" contains a comma.
    # If pylint splits on commas, it will try to compile "(foo{1" and "3})", which are invalid.
    # If fixed, it should treat the whole string as one regex or handle escaping correctly.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write('[tool.pylint.basic]\n')
        # Note: The issue report uses INI style, but modern pylint (3.0) often uses TOML.
        # However, the issue description shows [tool.pylint.basic] which is TOML syntax.
        # Let's use TOML format as indicated by the header in the issue.
        f.write('bad-names-rgxs = ["(foo{1,3})"]\n')
        temp_toml = f.name

    try:
        from pylint.lint import Run
        
        # We need to check if pylint crashes during initialization due to config parsing.
        # We run pylint with the specific config file.
        # exit=False prevents sys.exit, allowing us to catch exceptions or inspect state.
        try:
            # In Pylint 3.0, the argument might be bad-names-rgxs or similar.
            # The issue title says "bad-names-rgxs".
            # We pass the rcfile option.
            run = Run([temp_py, f"--rcfile={temp_toml}"], exit=False)
            
            # If we reach here, initialization succeeded.
            # We should also verify that the regex was actually compiled correctly.
            # We can inspect the linter's config.
            linter = run.linter
            
            # Access the config value for bad_names_rgxs
            # In pylint 3.0, options are often accessed via linter.config
            rgxs = getattr(linter.config, 'bad_names_rgxs', None)
            
            if rgxs is None:
                # Try alternative naming conventions if necessary
                rgxs = getattr(linter.config, 'bad_names_rgx', None)
                
            assert rgxs is not None, "Could not find bad_names_rgxs in config"
            
            # rgxs should be a list of compiled regex objects or patterns
            # If it's a list of patterns, check if it contains our pattern
            # If it's compiled, check if it matches "foo"
            
            # In pylint, _regexp_csv_transfomer returns a list of compiled re.Pattern objects
            assert isinstance(rgxs, list), f"Expected list of regexes, got {type(rgxs)}"
            assert len(rgxs) > 0, "Expected at least one regex"
            
            # Check if the first regex compiles and works as expected
            # The pattern is "(foo{1,3})". It should match "foo", "fooo", etc.
            pattern_obj = rgxs[0]
            
            # Verify it's a compiled regex
            import re
            assert hasattr(pattern_obj, 'match'), "Item in rgxs is not a compiled regex"
            
            # Test matching
            assert pattern_obj.match("foo"), "Regex did not match 'foo'"
            assert pattern_obj.match("fooo"), "Regex did not match 'fooo'"
            
            # If we got here, the bug is fixed.
            sys.exit(0)
            
        except SystemExit as e:
            # If pylint exits with non-zero during init, it likely crashed
            if e.code != 0:
                sys.exit(1)
            else:
                sys.exit(0)
        except Exception as e:
            # Any other exception during setup (like re.error) indicates the bug is present
            print(f"Error during pylint run: {e}")
            sys.exit(1)
            
    finally:
        # Cleanup
        if os.path.exists(temp_py):
            os.unlink(temp_py)
        if os.path.exists(temp_toml):
            os.unlink(temp_toml)

if __name__ == "__main__":
    main()
