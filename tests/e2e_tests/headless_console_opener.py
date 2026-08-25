"""Headless replacement for webbrowser.open(), used during e2e CI runs.

Loading the PythonAnywhere console URL triggers PA's client-side JS to open a
websocket and spawn the actual bash console process server-side -- something
the API alone cannot do. This module drives that page load with a headless,
pre-authenticated browser session instead of a real, interactive browser.

Resolved via DSD_PYTHONANYWHERE_CONSOLE_OPENER=e2e_tests.headless_console_opener:open_console
(see dsd_pythonanywhere.client._get_console_opener). The plugin's tests/ dir
must be on PYTHONPATH for that dotted path to resolve in the deploy subprocess.
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

AUTH_STATE_PATH = Path(os.getenv("PA_AUTH_STATE_PATH", "pa_auth_state.json"))


def open_console(url: str) -> None:
    """Load a PA console URL headlessly to trigger server-side console startup."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(AUTH_STATE_PATH))
        page = context.new_page()
        page.goto(url)
        if "/login/" in page.url:
            raise RuntimeError(
                f"PA_AUTH_STATE session appears expired (redirected to login for {url})"
            )
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)
        browser.close()
