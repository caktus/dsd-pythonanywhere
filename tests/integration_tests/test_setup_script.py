"""Integration tests for the PythonAnywhere setup.sh script."""

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
    # Use the current Python version available on CI for testing
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"

    # Create a minimal git repository with a requirements.txt file
    source_repo = tmp_path / "source_repo"
    source_repo.mkdir()
    (source_repo / "requirements.txt").write_text("django\n")
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
        ["bash", str(script_path), repo_url, dir_name, python_version],
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
    assert "ON_PYTHONANYWHERE=true" in env_content
    assert "DJANGO_SECRET_KEY=" in env_content

    # Verify secret key is not empty
    for line in env_content.splitlines():
        if line.startswith("DJANGO_SECRET_KEY="):
            secret_key = line.split("=", 1)[1]
            assert len(secret_key) == 50
