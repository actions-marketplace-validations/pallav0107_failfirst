"""
Check script for sphinx-doc/sphinx issue regarding TypeError in autodoc mock
for generic-typed classes.

The issue is that `mock._make_subclass` attempts to concatenate a str to a TypeVar,
causing a TypeError when building docs for generically-typed classes.

This script reproduces the core logic of `_make_subclass` from `sphinx.ext.autodoc.mock`
and checks if it handles Generic types correctly without raising a TypeError.
"""

import sys
import typing
from typing import TypeVar, Generic

# We need to simulate the behavior of sphinx.ext.autodoc.mock._make_subclass
# In Sphinx 3.1/3.2, the code looked something like this:
# def _make_subclass(name, base):
#     ...
#     return type(name, (base,), {'__module__': __name__})
#
# The error occurred because when `base` was a Generic alias or involved TypeVars,
# internal string concatenation or representation logic failed.
# Specifically, the issue mentions concatenating a str to a TypeVar.

def check_mock_make_subclass():
    """
    Reproduce the specific failure mode in sphinx.ext.autodoc.mock._make_subclass
    related to Generic types.
    """
    try:
        from sphinx.ext.autodoc.mock import _make_subclass
    except ImportError:
        # If the module doesn't exist or structure changed significantly, 
        # we might need to look elsewhere, but for v3.2 it should be there.
        print("Could not import _make_subclass")
        sys.exit(1)

    T = TypeVar('T')

    class MyGenericClass(Generic[T]):
        pass

    # The bug manifests when trying to create a mock subclass of a generic class.
    # The original error was: TypeError: can only concatenate str (not "TypeVar") to str
    # This happened inside _make_subclass when it tried to construct a name or handle bases.
    
    try:
        # Attempt to create a subclass of the generic class using the mock helper
        # In the buggy version, this would fail during the type creation or name handling
        # if the implementation tried to do string operations on the TypeVar itself.
        
        # Let's try creating a mock of the generic class directly via _make_subclass
        # The function signature is roughly _make_subclass(name, base)
        
        # We pass the generic class as the base
        mock_class = _make_subclass("MockMyGenericClass", MyGenericClass)
        
        # If we got here, no TypeError was raised during creation.
        # However, the issue might also occur when the base is a specialized generic, e.g., MyGenericClass[int]
        # But the report says "generically-typed class", usually meaning the class definition itself.
        
        # Let's also try with a parameterized generic if possible, as that's often where repr issues lie
        try:
            ParameterizedGeneric = MyGenericClass[int]
            mock_class_param = _make_subclass("MockParameterizedGeneric", ParameterizedGeneric)
        except TypeError:
            # If parameterized fails but unparameterized worked, it's still a bug regarding generics
            raise AssertionError("Failed to create mock subclass for parameterized generic type")

    except TypeError as e:
        # If we get a TypeError, especially one mentioning concatenation of str and TypeVar,
        # the bug is present.
        error_msg = str(e)
        print(f"TypeError caught: {error_msg}")
        # Check if it matches the reported symptom
        if "can only concatenate str" in error_msg or "TypeVar" in error_msg:
            raise AssertionError(f"The bug is present: {e}")
        else:
            # Some other TypeError, might still be considered a failure in this context
            raise AssertionError(f"Unexpected TypeError indicating the bug or a related issue: {e}")
            
    except Exception as e:
        raise AssertionError(f"Unexpected exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    check_mock_make_subclass()
    print("Check passed: No TypeError when mocking generic-typed classes.")
    sys.exit(0)
