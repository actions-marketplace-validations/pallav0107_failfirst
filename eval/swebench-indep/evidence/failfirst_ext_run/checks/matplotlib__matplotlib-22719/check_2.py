import warnings
import matplotlib.pyplot as plt
import numpy as np

# Ensure we are testing the specific scenario described in the issue
def check_empty_category_plot():
    """
    Reproduces the bug where plotting empty data on an axis with category units
    raises a confusing MatplotlibDeprecationWarning or ConversionError.
    
    Expected behavior (Fixed): No warning is raised, and the plot command succeeds.
    Buggy behavior: MatplotlibDeprecationWarning is raised regarding passing numbers
    through unit converters, even though no numbers were passed (just empty lists/arrays).
    """
    
    # Create figure and axis
    f, ax = plt.subplots()
    
    # Set up category units on the x-axis
    ax.xaxis.update_units(["a", "b"])
    
    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered
        warnings.simplefilter("always")
        
        try:
            # This is the line that triggers the bug in version 3.5.1
            ax.plot([], [])
        except Exception as e:
            # If it raises an exception like ConversionError, that's also a failure
            # of the expected smooth handling of empty data.
            raise AssertionError(f"Plotting empty data raised an exception: {type(e).__name__}: {e}")
        
        # Check for the specific deprecation warning mentioned in the issue
        deprecation_warnings = [
            warning for warning in w 
            if issubclass(warning.category, DeprecationWarning) 
            and "Support for passing numbers through unit converters" in str(warning.message)
        ]
        
        if deprecation_warnings:
            raise AssertionError(
                f"Unexpected MatplotlibDeprecationWarning raised for empty data: "
                f"{deprecation_warnings[0].message}"
            )

    plt.close(f)

if __name__ == "__main__":
    check_empty_category_plot()
    print("Check passed: No spurious deprecation warning for empty category data.")
