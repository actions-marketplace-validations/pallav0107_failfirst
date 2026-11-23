import sys
import enum
import inspect
from unittest.mock import Mock, patch

# Create a test enum
class MyEnum(enum.Enum):
    ValueA = 10
    ValueB = 20

# Define a function with an enum default value
def ugly_enum_func(e: MyEnum = MyEnum.ValueA) -> None:
    pass

# We need to check how Sphinx's autodoc/inspect module handles the signature.
# The issue is about the rendering of default values in signatures.
# Specifically, <MyEnum.ValueA: 10> vs MyEnum.ValueA.

# Let's look at sphinx.util.inspect which handles signature processing.
try:
    from sphinx.util.inspect import signature, stringify_signature
except ImportError:
    # Fallback for older versions or different structure
    from sphinx.ext.autodoc import process_signature
    # This path is harder to test directly without full app setup.
    # Let's stick to sphinx.util.inspect if available (Sphinx 4.x has it).
    sys.exit(1)

def get_default_repr():
    """
    Get the string representation of the default argument as processed by Sphinx.
    """
    sig = signature(ugly_enum_func)
    # stringify_signature converts the signature object to a string
    str_sig = stringify_signature(sig)
    return str_sig

def main():
    result = get_default_repr()
    
    # The issue states that the ugly rendering is:
    # ugly_enum_func(e: ugly_enum.MyEnum = <MyEnum.ValueA: 10>) -> None
    
    # The expected/correct rendering should be:
    # ugly_enum_func(e: MyEnum = MyEnum.ValueA) -> None
    # Or at least not contain the angle-bracket repr like <MyEnum.ValueA: 10>
    
    # Check if the "ugly" repr is present
    if "<MyEnum.ValueA: 10>" in result:
        # Issue is still present (buggy behavior)
        raise AssertionError(f"Enum default value is rendered uglily: {result}")
    
    # Check if the "nice" repr is present
    # It might be just "MyEnum.ValueA" or similar
    if "MyEnum.ValueA" in result:
        # Issue is fixed
        print("Issue is fixed: Enum default value is rendered correctly.")
        sys.exit(0)
    else:
        # If neither is found, something else is wrong, but let's assume 
        # if the ugly one is gone, it's likely fixed or changed.
        # However, to be strict, we want the nice name.
        # Let's check if the result contains 'ValueA' without the angle brackets and colon value
        if "ValueA" in result and "<" not in result.split("=")[1].split(")")[0]:
             sys.exit(0)
        else:
             raise AssertionError(f"Unexpected signature format: {result}")

if __name__ == "__main__":
    main()
