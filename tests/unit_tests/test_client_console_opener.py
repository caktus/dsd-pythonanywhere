import webbrowser

import pytest

from dsd_pythonanywhere.client import _get_console_opener


def test_get_console_opener_defaults_to_webbrowser_open(monkeypatch):
    """Without the override env var, the default opener is webbrowser.open."""
    monkeypatch.delenv("DSD_PYTHONANYWHERE_CONSOLE_OPENER", raising=False)
    assert _get_console_opener() is webbrowser.open


def test_get_console_opener_resolves_dotted_path(monkeypatch):
    """The env var resolves a "module:function" path to a callable."""
    monkeypatch.setenv(
        "DSD_PYTHONANYWHERE_CONSOLE_OPENER",
        "test_client_console_opener:fake_opener",
    )
    assert _get_console_opener() is fake_opener


def test_get_console_opener_missing_function_raises(monkeypatch):
    """An unresolvable function name raises AttributeError."""
    monkeypatch.setenv(
        "DSD_PYTHONANYWHERE_CONSOLE_OPENER",
        "test_client_console_opener:does_not_exist",
    )
    with pytest.raises(AttributeError):
        _get_console_opener()


def fake_opener(url: str) -> None:
    """Used only as a resolution target in test_get_console_opener_resolves_dotted_path."""
