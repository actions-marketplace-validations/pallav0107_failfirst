import sys
import enum
from unittest.mock import MagicMock

# Mock sphinx components that might be heavy or require full app context
# We only need the signature processing logic which is often in sphinx.util.inspect or similar

class MyEnum(enum.Enum):
    ValueA = 10

def ugly_enum_func(e: MyEnum = MyEnum.ValueA) -> None:
    pass

def main():
    # Import the specific utility function responsible for formatting signatures/annotations.
    # In Sphinx 4.x, this logic is largely handled by sphinx.util.inspect.signature and 
    # the representation of objects.
    
    try:
        from sphinx.util.inspect import signature
        from sphinx.ext.autodoc import process_signature
        
        # Create a mock app to satisfy autodoc dependencies if needed, 
        # but let's try to hit the core inspection logic first.
        
        # The issue is about how the default value is represented in the signature string.
        # The expected behavior is "MyEnum.ValueA", the buggy behavior is "<MyEnum.ValueA: 10>".
        
        sig = signature(ugly_enum_func)
        
        # Get the string representation of the signature
        sig_str = str(sig)
        
        # The signature object itself might not fully render the default as desired without 
        # the autodoc layer, but let's check the parameter default representation.
        
        # Let's look at how sphinx formats the annotation/default.
        # Often, the issue lies in `sphinx.util.inspect.object_description` or similar helpers.
        
        from sphinx.util.inspect import object_description
        
        desc = object_description(MyEnum.ValueA)
        
        # If fixed, desc should be 'MyEnum.ValueA' or similar clean representation.
        # If buggy, it contains '<...>' or the repr().
        
        # According to the issue, the rendered signature contains `<MyEnum.ValueA: 10>`.
        # This comes from the standard repr() of the Enum.
        # A fix would likely override this to use the qualified name or similar.
        
        # Let's check if the description is "clean" (does not contain angle brackets with colon inside)
        # or specifically matches the expected format.
        
        # Expected: MyEnum.ValueA
        # Buggy: <MyEnum.ValueA: 10>
        
        # Note: The exact expected string might depend on implementation details (e.g., module prefix).
        # The issue example shows `ugly_enum.MyEnum = MyEnum.ValueA`. 
        # So we expect the default value part to NOT look like a raw repr.
        
        # Let's assert that the object_description does NOT contain the ugly repr format.
        # The ugly format is characterized by starting with '<' and containing ':'.
        
        is_ugly = desc.startswith('<') and ':' in desc and desc.endswith('>')
        
        # However, some valid reprs might look like that? No, Enum repr is specifically <Enum.Member: value>.
        # A clean representation would be just the name or qualified name.
        
        # Let's be precise: The issue says it renders as `<MyEnum.ValueA: 10>`.
        # We want it to render as `MyEnum.ValueA`.
        
        # Let's check if desc equals the expected clean string.
        # It might be `MyEnum.ValueA` or `ugly_enum.MyEnum.ValueA` depending on context.
        # But definitely not the repr.
        
        if is_ugly:
            raise AssertionError(f"Enum value description is still ugly: {desc}")
            
        # Additional check: ensure it looks like a proper attribute access
        if '.' not in desc:
             # Might be just 'ValueA'? The issue expects `MyEnum.ValueA`.
             # Let's assume the fix makes it look like code.
             pass
        
        # Let's verify against the specific expected substring from the issue
        # Expected: MyEnum.ValueA
        if "MyEnum.ValueA" not in desc:
             # It might be wrapped or different, but if it's not ugly, it might be acceptable?
             # Let's stick to the negative check: it must NOT be the ugly repr.
             # But to be safe, let's check if it matches the expected pattern more closely.
             # The fix in Sphinx usually involves using `qualname` or similar.
             
             # If it's not ugly, but also not what we expect, is it correct?
             # The issue explicitly wants `MyEnum.ValueA`.
             
             # Let's check if the string is exactly 'MyEnum.ValueA' or contains it.
             # In many contexts, it will be just the enum member's representation.
             
             # Let's rely on the fact that the bug is the presence of angle brackets and colon.
             # If those are gone, it's likely fixed.
             
             # However, to be strict:
             assert "MyEnum.ValueA" in desc, f"Expected 'MyEnum.ValueA' in description, got: {desc}"

        sys.exit(0)

    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        sys.exit(1)
    except AssertionError as e:
        print(f"Assertion failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
