from astropy.table import Table
from io import StringIO

# Generate table with specific floating point values
t = Table([(1.23875234858e-24, 3.2348748432e-15), (2, 4)], names=('a', 'b'))

# Write to HTML with a specific format for column 'a'
# The format lambda forces scientific notation with 2 decimal places
with StringIO() as sp:
    t.write(sp, format="html", formats={"a": lambda x: f"{x:.2e}"})
    html_output = sp.getvalue()

# Check if the formatted values are present in the output
# Expected formatted values:
# 1.23875234858e-24 -> 1.24e-24
# 3.2348748432e-15 -> 3.23e-15

assert "1.24e-24" in html_output, f"Expected '1.24e-24' in HTML output but got:\n{html_output}"
assert "3.23e-15" in html_output, f"Expected '3.23e-15' in HTML output but got:\n{html_output}"

# Ensure the unformatted raw values are NOT present (to be sure formatting was applied)
# Note: The raw value 1.23875234858e-24 might appear as part of the string representation 
# if formatting failed, but since we check for the specific formatted string, this is sufficient.
# However, let's explicitly ensure the long raw representation isn't there if it differs significantly.
# The raw repr in Python for 1.23875234858e-24 is '1.23875234858e-24'.
assert "1.23875234858e-24" not in html_output, f"Raw unformatted value '1.23875234858e-24' found in HTML output, meaning formats were ignored:\n{html_output}"

print("Check passed: HTML output respects the 'formats' argument.")
