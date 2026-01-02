"""Basic happy path tests for the PythonAnywhere setup.sh script."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def setup_script_result(tmp_path_factory) -> dict:
    """Run setup.sh once and return the result along with paths for testing."""
    tmp_path = tmp_path_factory.mktemp("setup_script")
    script_path = Path(__file__).parent.parent.parent / "scripts" / "setup.sh"
    dir_name = "test_project"
    django_project_name = "mysite"
    # Use the current Python version available on CI for testing
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"

    # Create a minimal git repository with a requirements.txt file and Django project
    source_repo = tmp_path / "source_repo"
    source_repo.mkdir()
    (source_repo / "requirements.txt").write_text("django\n")

    # Create a minimal Django project structure with wsgi.py and settings.py
    django_project_dir = source_repo / django_project_name
    django_project_dir.mkdir()
    (django_project_dir / "__init__.py").write_text("")
    (django_project_dir / "wsgi.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")\n'
    )
    (django_project_dir / "settings.py").write_text(
        """
SECRET_KEY = 'test-secret-key'
DEBUG = True
INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.staticfiles']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'db.sqlite3'}}
STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
"""
    )
    # Create minimal manage.py
    (source_repo / "manage.py").write_text(
        """#!/usr/bin/env python
import os
import sys
if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
"""
    )

    subprocess.run(["git", "init"], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )
    repo_url = source_repo.as_uri()
    try:
        result = subprocess.run(
            [
                "bash",
                str(script_path),
                repo_url,
                dir_name,
                django_project_name,
                python_version,
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print("Setup script failed with the following output:")
        print(e.stdout)
        print(e.stderr)
        raise

    return {
        "result": result,
        "tmp_path": tmp_path,
        "venv_path": tmp_path / "venv",
        "project_path": tmp_path / dir_name,
        "django_project_name": django_project_name,
    }


def test_setup_script_creates_venv(setup_script_result):
    """setup.sh creates a virtual environment."""
    assert setup_script_result["result"].returncode == 0
    assert setup_script_result["venv_path"].exists()
    assert (setup_script_result["venv_path"] / "bin" / "activate").exists()


def test_setup_script_clones_repo(setup_script_result):
    """setup.sh clones the repository."""
    assert setup_script_result["project_path"].exists()
    assert (setup_script_result["project_path"] / "requirements.txt").exists()


def test_setup_script_creates_env_file(setup_script_result):
    """setup.sh creates a .env file with required environment variables."""
    assert ".env file created." in setup_script_result["result"].stdout

    env_file = setup_script_result["project_path"] / ".env"
    assert env_file.exists()

    env_content = env_file.read_text()
    assert "DEBUG=TRUE" in env_content
    assert "ON_PYTHONANYWHERE=TRUE" in env_content
    assert "SECRET_KEY=" in env_content

    # Verify secret key is not empty
    for line in env_content.splitlines():
        if line.startswith("SECRET_KEY="):
            secret_key = line.split("=", 1)[1]
            assert len(secret_key) == 50


def test_setup_script_runs_migrate(setup_script_result):
    """setup.sh runs Django migrations."""
    stdout = setup_script_result["result"].stdout
    assert "Running migrations and collectstatic..." in stdout
    # Check that migrations ran (either applied or no migrations to apply)
    assert "Operations to perform:" in stdout or "No migrations to apply" in stdout
