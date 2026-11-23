from astropy.table import Table
from io import StringIO

# Generate table with specific floating point values
t = Table([(1.23875234858e-24, 3.2348748432e-15), (2, 4)], names=('a', 'b'))

# Write to HTML with a specific format for column 'a'
with StringIO() as sp:
    t.write(sp, format="html", formats={"a": lambda x: f"{x:.2e}"})
    html_output = sp.getvalue()

# Check if the formatted values are present in the output
# The format {:.2e} should produce 1.24e-24 and 3.23e-15
assert "1.24e-24" in html_output, f"Expected '1.24e-24' in HTML output, but got:\n{html_output}"
assert "3.23e-15" in html_output, f"Expected '3.23e-15' in HTML output, but got:\n{html_output}"

# Ensure the unformatted full-precision values are NOT present
assert "1.23875234858e-24" not in html_output, f"Unformatted value '1.23875234858e-24' found in HTML output:\n{html_output}"
assert "3.2348748432e-15" not in html_output, f"Unformatted value '3.2348748432e-15' found in HTML output:\n{html_output}"

print("Check passed: HTML output respects the 'formats' argument.")
