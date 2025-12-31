import os
from pathlib import Path

from dotenv import load_dotenv

# Set the project directory explicitly for PythonAnywhere
# The WSGI file lives in /var/www/, not in the project directory
project_dir = Path.home() / "{{ repo_name }}"

# Ensure the project directory is in the PYTHONPATH
if str(project_dir) not in os.sys.path:
    os.sys.path.insert(0, str(project_dir))

# Load deployed environment variables from the project's .env file
load_dotenv(project_dir / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{{ django_project_name }}.settings")

from django.core.wsgi import get_wsgi_application  # noqa E402

application = get_wsgi_application()
