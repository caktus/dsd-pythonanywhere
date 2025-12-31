import sys
from pathlib import Path

import pytest
from django_simple_deploy.management.commands.utils.command_errors import DSDCommandError

from dsd_pythonanywhere.platform_deployer import (
    PLUGIN_REQUIREMENTS,
    PlatformDeployer,
    dsd_config,
)


def test_modify_gitignore(tmp_path: Path, monkeypatch):
    """_modify_gitignore adds patterns correctly."""
    deployer = PlatformDeployer()
    monkeypatch.setattr(dsd_config, "git_path", tmp_path)
    monkeypatch.setattr(dsd_config, "stdout", sys.stdout)

    gitignore_path = tmp_path / ".gitignore"

    # Test when .gitignore does not exist
    deployer._modify_gitignore()
    assert gitignore_path.exists()
    contents = gitignore_path.read_text()
    assert ".env" in contents

    # Test when .gitignore exists but does not contain .env
    gitignore_path.write_text("*.pyc\n__pycache__/")
    deployer._modify_gitignore()
    contents = gitignore_path.read_text()
    assert ".env" in contents

    # Test when .gitignore already contains .env
    gitignore_path.write_text(".env\n*.pyc\n__pycache__/")
    deployer._modify_gitignore()
    contents = gitignore_path.read_text()
    assert contents.count(".env") == 1


def test_modify_settings(tmp_path: Path, monkeypatch):
    """_modify_settings modifies settings.py as expected."""
    settings_path = tmp_path / "settings.py"
    settings_content = "# Existing settings"
    settings_path.write_text(settings_content)

    deployer = PlatformDeployer()
    monkeypatch.setattr(dsd_config, "settings_path", settings_path)
    monkeypatch.setattr(dsd_config, "stdout", sys.stdout)

    deployer._modify_settings()
    modified_content = settings_path.read_text()
    assert 'if os.getenv("ON_PYTHONANYWHERE"):' in modified_content


def test_add_requirements(tmp_path: Path, monkeypatch):
    """_add_requirements adds required packages."""
    requirements_path = tmp_path / "requirements.txt"
    requirements_content = "Django"
    requirements_path.write_text(requirements_content)

    deployer = PlatformDeployer()
    monkeypatch.setattr(dsd_config, "req_txt_path", requirements_path)
    monkeypatch.setattr(dsd_config, "stdout", sys.stdout)
    monkeypatch.setattr(dsd_config, "requirements", [])

    deployer._add_requirements()
    modified_content = requirements_path.read_text()
    for package in PLUGIN_REQUIREMENTS:
        assert package in modified_content


def test_validate_platform_missing_api_user(monkeypatch):
    """_validate_platform raises error when API_USER is missing."""
    monkeypatch.delenv("API_USER", raising=False)
    monkeypatch.setenv("API_TOKEN", "test_token")

    with pytest.raises(DSDCommandError, match="API_USER environment variable is not set"):
        deployer = PlatformDeployer()
        deployer._validate_platform()


def test_validate_platform_missing_api_token(monkeypatch):
    """_validate_platform raises error when API_TOKEN is missing."""
    monkeypatch.setenv("API_USER", "test_user")
    monkeypatch.delenv("API_TOKEN", raising=False)

    deployer = PlatformDeployer()
    with pytest.raises(DSDCommandError, match="API_TOKEN environment variable is not set"):
        deployer._validate_platform()


def test_validate_platform_api_connection_fails(monkeypatch, mocker):
    """_validate_platform raises error when API connection fails."""
    monkeypatch.setenv("API_USER", "test_user")
    monkeypatch.setenv("API_TOKEN", "test_token")

    deployer = PlatformDeployer()
    mock_request = mocker.patch.object(deployer.client, "request")
    mock_request.side_effect = Exception("Connection failed")

    with pytest.raises(DSDCommandError, match="Failed to connect to PythonAnywhere API"):
        deployer._validate_platform()


def test_validate_platform_success(monkeypatch, mocker):
    """_validate_platform succeeds with valid credentials."""
    monkeypatch.setenv("API_USER", "test_user")
    monkeypatch.setenv("API_TOKEN", "test_token")

    deployer = PlatformDeployer()
    mock_request = mocker.patch.object(deployer.client, "request")
    mock_response = mocker.Mock()
    mock_response.ok = True
    mock_request.return_value = mock_response

    # Should not raise any exception
    deployer._validate_platform()
