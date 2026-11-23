from astropy.table import Table
from io import StringIO

# Generate table with specific floating point values
t = Table([(1.23875234858e-24, 3.2348748432e-15), (2, 4)], names=('a', 'b'))

# Write to HTML with a custom format for column 'a'
with StringIO() as sp:
    t.write(sp, format="html", formats={"a": lambda x: f"{x:.2e}"})
    html_output = sp.getvalue()

# Check if the formatted values are present in the output
# The expected formatted values are 1.24e-24 and 3.23e-15
assert "1.24e-24" in html_output, f"Expected '1.24e-24' in HTML output but got:\n{html_output}"
assert "3.23e-15" in html_output, f"Expected '3.23e-15' in HTML output but got:\n{html_output}"

# Ensure the unformatted raw values are NOT present (to be sure formatting was applied)
# Note: 1.23875234858e-24 is the raw value. If formatting worked, it should be replaced.
assert "1.23875234858e-24" not in html_output, f"Raw unformatted value '1.23875234858e-24' found in HTML output, meaning formats were ignored:\n{html_output}"

print("Check passed: HTML output respects the 'formats' argument.")
