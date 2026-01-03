"""Basic smoke test to verify package installation."""

import sys
from pathlib import Path

# Verify package can be imported
import dsd_pythonanywhere

# Verify version is set
assert hasattr(dsd_pythonanywhere, "__version__"), "Missing __version__ attribute"
print(f"✓ Package version: {dsd_pythonanywhere.__version__}")

# Verify main exports exist
assert hasattr(dsd_pythonanywhere, "dsd_deploy"), "Missing dsd_deploy export"
assert hasattr(dsd_pythonanywhere, "dsd_get_plugin_config"), "Missing dsd_get_plugin_config export"
print("✓ Main exports found")

# Verify templates directory is included
package_path = Path(dsd_pythonanywhere.__file__).parent
templates_dir = package_path / "templates"
assert templates_dir.exists(), f"Templates directory not found at {templates_dir}"
assert templates_dir.is_dir(), f"Templates path exists but is not a directory: {templates_dir}"
print(f"✓ Templates directory found: {templates_dir}")

# Verify template files exist
expected_templates = ["settings.py", "wsgi.py", "dockerfile_example"]
for template in expected_templates:
    template_path = templates_dir / template
    assert template_path.exists(), f"Missing template file: {template}"
    print(f"  ✓ Found: {template}")

print("\n✅ All smoke tests passed!")
sys.exit(0)
