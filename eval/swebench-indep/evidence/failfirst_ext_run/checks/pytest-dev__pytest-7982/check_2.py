import os
import sys
import tempfile
import shutil

def main():
    # Create a temporary directory structure
    tmpdir = tempfile.mkdtemp()
    try:
        # Create a real test directory with a test file
        real_test_dir = os.path.join(tmpdir, "real_tests")
        os.makedirs(real_test_dir)
        
        test_file_path = os.path.join(real_test_dir, "test_example.py")
        with open(test_file_path, "w") as f:
            f.write("def test_foo():\n    pass\n")
        
        # Create a symlink to the real test directory
        symlink_test_dir = os.path.join(tmpdir, "linked_tests")
        os.symlink(real_test_dir, symlink_test_dir)
        
        # Import pytest's collection logic directly
        from _pytest.main import Session
        from _pytest.config import Config
        from _pytest.config.argparsing import Parser
        
        # We need to mimic how pytest collects files.
        # The core logic for file collection is in _pytest.main and _pytest.nodes
        # Specifically, we look at how pytest collects items from a path.
        
        # Let's use the internal API to check if the symlinked directory is collected.
        # We will use pytest's own collection mechanism via the Config object.
        
        # Create a minimal config
        from _pytest.config import PytestPluginManager
        from _pytest.config import Config
        
        pm = PytestPluginManager()
        config = Config.fromdictargs({}, [tmpdir])
        config._do_configure()
        
        # Get the session
        session = Session.from_config(config)
        
        # Perform collection on the tmpdir which contains both real_tests and linked_tests (symlink)
        # We specifically want to see if test_example.py inside linked_tests is collected.
        
        # The collect method of Session returns a list of nodes
        session.perform_collect()
        
        # Check if any collected item corresponds to the file inside the symlinked directory
        found_in_symlink = False
        for item in session.items:
            # item.nodeid or item.fspath can tell us where it came from
            # In pytest 6.2, items have 'path' attribute (py.path.local) or 'fspath'
            try:
                item_path = str(item.path)
            except AttributeError:
                item_path = str(item.fspath)
            
            if "linked_tests" in item_path and "test_example.py" in item_path:
                found_in_symlink = True
                break
        
        config._ensure_unconfigure()
        
        # Assert that the test file in the symlinked directory was collected
        assert found_in_symlink, "Test file in symlinked directory was not collected. Bug is present."
        
        return 0
        
    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    sys.exit(main())
