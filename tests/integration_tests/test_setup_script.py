"""Integration tests for the PythonAnywhere setup.sh script."""

import getpass
import subprocess
import sys
from pathlib import Path

import pytest

# --- Fixtures ---


@pytest.fixture(scope="module")
def setup_script_result(tmp_path_factory) -> dict:
    """Run setup.sh once and return the result along with paths for testing."""
    tmp_path = tmp_path_factory.mktemp("setup_script")
    script_path = Path(__file__).parent.parent.parent / "scripts" / "setup.sh"
    dir_name = "test_project"
    django_project_name = "mysite"
    # Use the current Python version available on CI for testing
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    # Use a temp directory for WSGI destination prefix
    wsgi_dest_prefix = tmp_path / "var_www"

    # Create a minimal git repository with a requirements.txt file and Django project
    source_repo = tmp_path / "source_repo"
    source_repo.mkdir()
    (source_repo / "requirements.txt").write_text("django\n")

    # Create a minimal Django project structure with wsgi.py
    django_project_dir = source_repo / django_project_name
    django_project_dir.mkdir()
    (django_project_dir / "wsgi.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")\n'
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

    result = subprocess.run(
        [
            "bash",
            str(script_path),
            repo_url,
            dir_name,
            django_project_name,
            python_version,
            str(wsgi_dest_prefix),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    return {
        "result": result,
        "tmp_path": tmp_path,
        "venv_path": tmp_path / "venv",
        "project_path": tmp_path / dir_name,
        "django_project_name": django_project_name,
        "wsgi_dest_prefix": wsgi_dest_prefix,
    }


# --- Test setup.sh script ---


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


def test_setup_script_copies_wsgi_file(setup_script_result):
    """setup.sh copies WSGI file to the destination prefix."""
    username = getpass.getuser()
    domain = f"{username}.pythonanywhere.com"
    wsgi_filename = f"{domain.replace('.', '_')}_wsgi.py"
    wsgi_dest = setup_script_result["wsgi_dest_prefix"] / wsgi_filename

    assert "WSGI file copied." in setup_script_result["result"].stdout
    assert wsgi_dest.exists()
    assert "DJANGO_SETTINGS_MODULE" in wsgi_dest.read_text()
