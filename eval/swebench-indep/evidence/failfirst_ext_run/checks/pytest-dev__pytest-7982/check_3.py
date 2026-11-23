import os
import sys
import tempfile
import shutil

def main():
    # Create a temporary directory structure to test symlink collection
    tmpdir = tempfile.mkdtemp()
    try:
        # Create a real directory with a test file
        real_dir = os.path.join(tmpdir, "real_tests")
        os.makedirs(real_dir)
        
        test_file_path = os.path.join(real_dir, "test_example.py")
        with open(test_file_path, "w") as f:
            f.write("def test_pass():\n    pass\n")
        
        # Create a symlink to the real directory inside another directory
        link_dir = os.path.join(tmpdir, "linked_tests")
        os.symlink(real_dir, link_dir)
        
        # Import pytest's collection mechanism directly
        from _pytest.main import Session
        from _pytest.config import Config
        from _pytest.config.argparsing import Parser
        
        # We need to create a minimal config to use the collector
        # Let's use pytest's internal API to collect tests from the symlinked directory
        
        # Create a root path for collection
        root_path = tmpdir
        
        # Initialize pytest config
        from _pytest.config import PytestPluginManager
        pm = PytestPluginManager()
        config = Config.fromdictargs({}, [root_path], plugins=[], _ispytest=True)
        config._do_configure()
        
        # Create a session
        session = Session.from_config(config)
        
        # Perform collection on the symlinked directory specifically
        # We want to check if tests inside the symlinked directory are collected
        
        # Use the internal collection logic
        from _pytest.python import Module
        from _pytest.pathlib import visit
        
        # Let's try to collect using the standard pytest collection entry point but inspect what gets collected
        # A simpler approach: use pytest's path traversal which is where the bug was
        
        # The bug is in _pytest/pathlib.py or similar where follow_symlinks=False was added
        # Let's check if the symlinked directory is traversed
        
        # Import the relevant function that handles directory traversal
        # In pytest 6.1+, the regression was introduced by adding follow_symlinks=False
        
        # Let's use pytest's own collection to see if it picks up the test via the symlink
        # We'll collect from the tmpdir which contains both real_tests and linked_tests (symlink)
        
        # Actually, let's just check if pytest collects the test file through the symlink
        # by examining the items collected when we specify the symlinked path
        
        # Re-initialize config pointing to the symlinked directory
        config2 = Config.fromdictargs({}, [link_dir], plugins=[], _ispytest=True)
        config2._do_configure()
        session2 = Session.from_config(config2)
        
        # Trigger collection
        session2.perform_collect()
        
        # Check if any items were collected
        collected_items = session2.items
        
        # If the bug is present (follow_symlinks=False), no tests will be collected from the symlinked dir
        # If the bug is fixed, the test should be collected
        
        assert len(collected_items) > 0, f"Expected at least one test item to be collected from symlinked directory, but got {len(collected_items)} items. Symlinked directories are not being followed."
        
        # Verify it's the correct test
        assert collected_items[0].name == "test_pass", f"Expected test 'test_pass', got '{collected_items[0].name}'"
        
        config2._ensure_unconfigure()
        config._ensure_unconfigure()
        
        print("SUCCESS: Symlinked directories are correctly followed during test collection.")
        return 0
        
    except AssertionError as e:
        print(f"FAILURE: {e}")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
