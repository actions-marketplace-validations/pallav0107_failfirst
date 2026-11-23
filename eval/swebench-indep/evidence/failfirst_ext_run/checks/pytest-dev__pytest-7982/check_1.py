import os
import sys
import tempfile
import shutil

def main():
    # Import pytest internals to check collection behavior without running pytest CLI
    from _pytest.config import Config
    from _pytest.main import Session
    from _pytest.python import Package
    import py.path as py_path
    
    # Create a temporary directory structure with a symlinked directory
    tmpdir = tempfile.mkdtemp()
    try:
        # Create real test directory with a test file
        real_test_dir = os.path.join(tmpdir, "real_tests")
        os.makedirs(real_test_dir)
        
        test_file = os.path.join(real_test_dir, "test_example.py")
        with open(test_file, "w") as f:
            f.write("def test_foo():\n    pass\n")
        
        # Create a directory that will contain the symlink
        work_dir = os.path.join(tmpdir, "work")
        os.makedirs(work_dir)
        
        # Create symlink to the real test directory
        symlink_path = os.path.join(work_dir, "linked_tests")
        os.symlink(real_test_dir, symlink_path)
        
        # Now use pytest's internal collection mechanism to see if it collects tests from the symlinked directory
        # We need to mimic what pytest does during collection
        
        from _pytest.config import get_config
        from _pytest.main import resolve_collection_argument
        
        # Create a minimal config
        config = get_config()
        config.parse([work_dir])
        
        # Create a session
        session = Session.from_config(config)
        
        # Perform collection starting from the work directory
        # The key is whether the symlinked directory 'linked_tests' is followed
        
        # Use the internal collection API
        from _pytest.main import perform_collect
        
        # Let's directly check how pytest handles symlinks in path resolution
        # In pytest 6.1+, there was a change that added follow_symlinks=False
        
        # Check the actual collection result
        items = []
        
        # We'll manually trigger collection on the work_dir
        # First, let's see what paths pytest considers
        
        from _pytest.python import pytest_collect_file
        from _pytest.nodes import Collector
        
        # A more direct approach: check if pytest's filesystem walker follows symlinks
        # Look at _pytest/main.py or _pytest/legacypath.py for the relevant code
        
        # Actually, let's use the public-ish API: collect from the session
        session.perform_collect([work_dir], genitems=True)
        
        # Get all collected items
        collected_items = list(session.items)
        
        # Check if any item comes from the symlinked directory
        found_in_symlink = False
        for item in collected_items:
            # Get the file path of the test item
            if hasattr(item, 'fspath'):
                item_path = str(item.fspath)
            elif hasattr(item, 'path'):
                item_path = str(item.path)
            else:
                continue
            
            # Check if this path is within the symlinked directory
            # The symlink path is work_dir/linked_tests
            # Real path would resolve to real_test_dir
            # But we want to know if files UNDER the symlink were collected
            
            # Normalize paths for comparison
            norm_item_path = os.path.normpath(item_path)
            norm_symlink_path = os.path.normpath(symlink_path)
            
            if norm_item_path.startswith(norm_symlink_path + os.sep) or norm_item_path == norm_symlink_path:
                found_in_symlink = True
                break
            
            # Also check if the item's module file is physically inside the real_test_dir
            # but was reached via the symlink
            # This is trickier. Let's check if the collection included test_example.py
        
        # Alternative: check if test_example.py was collected at all
        # It should be collected because it's reachable via the symlink
        test_collected = False
        for item in collected_items:
            if hasattr(item, 'name') and item.name == 'test_foo':
                test_collected = True
                break
            if hasattr(item, 'originalname') and item.originalname == 'test_foo':
                test_collected = True
                break
        
        # The issue states that symlinked directories are NOT collected (skipped over)
        # So if the fix is applied, test_foo SHOULD be collected
        # If the bug is present, test_foo will NOT be collected
        
        assert test_collected, "Test file in symlinked directory was not collected. The bug is still present."
        
    finally:
        shutil.rmtree(tmpdir)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
