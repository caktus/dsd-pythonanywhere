from pathlib import Path
import sys

from dsd_pythonanywhere.platform_deployer import (
    PlatformDeployer,
    dsd_config,
    PLUGIN_REQUIREMENTS,
)


def test_modify_gitignore(tmp_path: Path, monkeypatch):
    """Test that _modify_gitignore adds patterns correctly."""
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
    """Look for one of expected modified lines in settings.py."""
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
    """Test that _add_requirements adds required packages."""
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
