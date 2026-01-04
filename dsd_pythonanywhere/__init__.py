try:
    from importlib.metadata import version

    __version__ = version("dsd-pythonanywhere")
except Exception:
    __version__ = "unknown"

from .deploy import dsd_deploy, dsd_get_plugin_config  # noqa: F401
