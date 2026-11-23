import sys
import enum

# Define a minimal Enum to reproduce the issue
class MyEnum(enum.Enum):
    ValueA = 10

# We need to check how Sphinx renders this enum in a signature.
# The core of the issue is in sphinx.util.inspect.signature or similar utilities
# that convert default values to strings for documentation.

# Let's look at how sphinx handles this internally.
# In Sphinx 4.x, the rendering of signatures often relies on sphinx.util.typing or
# sphinx.ext.autodoc's handling of defaults.

# However, we can test the specific utility function that formats the default value.
# The issue states that <MyEnum.ValueA: 10> is shown instead of MyEnum.ValueA.

# Let's try to import the relevant part of Sphinx that handles string representation
# of objects in signatures. In newer versions, this might be in sphinx.util.inspect
# or handled by repr() calls that are overridden.

# A common place where this happens is in the `formatvalue` logic within autodoc.
# But a more direct way is to check if Sphinx has a utility that "pretty prints" 
# enum values.

# Let's check sphinx.util.typing or sphinx.ext.autodoc.preserve_defaults 
# (if available) or just the general mechanism.

# Actually, the most robust way without building a full doctree is to check
# the behavior of `sphinx.util.inspect.stringify_signature` or similar if it exists,
# or directly check how the default is converted.

# In Sphinx 4.1, the code that handles this is likely in `sphinx.ext.autodoc`.
# When autodoc processes a function, it gets the signature using `inspect.signature`.
# Then it converts the parameters to strings.

# Let's simulate what autodoc does.
import inspect

def ugly_enum_func(e: MyEnum = MyEnum.ValueA) -> None:
    pass

sig = inspect.signature(ugly_enum_func)
param = sig.parameters['e']
default_value = param.default

# The raw repr is what the user complains about:
raw_repr = repr(default_value)
assert raw_repr == "<MyEnum.ValueA: 10>", "Precondition: standard repr is ugly"

# Now, how does Sphinx format this?
# In Sphinx 4.1, there is a function `sphinx.util.inspect.object_description` 
# or similar that might be used. Or it might use `sphinx.ext.autodoc`'s internal helpers.

# Let's try to import the specific helper that formats default values.
# In Sphinx 4.1, `sphinx.util.typing.stringify` is for types.
# For values, `sphinx.util.inspect` has some helpers.

try:
    from sphinx.util.inspect import object_description
    # This function is used to describe objects in error messages and potentially signatures
    desc = object_description(default_value)
except ImportError:
    # Fallback or different version
    try:
        from sphinx.ext.autodoc import formatvalue
        # formatvalue is a method of Documenter, harder to call directly.
        # Let's look for another way.
        
        # In Sphinx 4.1, the rendering of enums was improved.
        # Let's check if there is a specific utility for this.
        
        # Another candidate: sphinx.util.nodes.make_refnode? No.
        
        # Let's look at the actual fix for this issue. 
        # The issue is that enum.__repr__ includes the value.
        # Sphinx should ideally use enum.__str__ or a custom formatter.
        
        # If the fix is applied, Sphinx should render it as MyEnum.ValueA.
        
        # Let's try to find the function that converts the default to a string in signatures.
        # It is likely in `sphinx.ext.autodoc.TypeHintsFormatter` or similar.
        
        # Actually, a key function is `sphinx.util.inspect.signature` which returns a Signature object
        # that has been stringified.
        
        from sphinx.util.inspect import signature as sphinx_signature
        
        # Get the signature as Sphinx sees it
        sphinx_sig = sphinx_signature(ugly_enum_func)
        
        # The string representation of the signature
        sig_str = str(sphinx_sig)
        
        # The expected behavior is that it contains "MyEnum.ValueA" and NOT "<MyEnum.ValueA: 10>"
        # Note: The signature string might include the annotation too.
        
        # Let's print it to debug if needed, but we must assert.
        # Expected: "(e: ugly_enum.MyEnum = MyEnum.ValueA) -> None" or similar
        # But since we are not in a module named ugly_enum, it might just be __main__.MyEnum
        
        # Let's check if the ugly repr is present
        if "<MyEnum.ValueA: 10>" in sig_str:
            raise AssertionError("Enum is rendered with ugly repr: " + sig_str)
        
        # Check if the nice version is present
        if "MyEnum.ValueA" not in sig_str:
            raise AssertionError("Enum is not rendered correctly: " + sig_str)
            
        sys.exit(0)
        
    except ImportError:
        sys.exit(1)

# If object_description worked, let's check it
if "<MyEnum.ValueA: 10>" in desc:
    raise AssertionError("object_description still uses ugly repr: " + desc)

if "MyEnum.ValueA" not in desc:
    raise AssertionError("object_description does not contain expected enum name: " + desc)

sys.exit(0)
