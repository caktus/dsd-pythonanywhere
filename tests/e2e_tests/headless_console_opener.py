"""Headless replacement for webbrowser.open(), used during e2e CI runs.

Loading the PythonAnywhere console URL triggers PA's client-side JS to open a
websocket and spawn the actual bash console process server-side -- something
the API alone cannot do. This module drives that page load with a headless
browser, logging in with a username/password first since the console page
requires an authenticated session.

Resolved via DSD_PYTHONANYWHERE_CONSOLE_OPENER=e2e_tests.headless_console_opener:open_console
(see dsd_pythonanywhere.client._get_console_opener). The plugin's tests/ dir
must be on PYTHONPATH for that dotted path to resolve in the deploy subprocess.
"""

import os

from playwright.sync_api import sync_playwright

LOGIN_URL = "https://www.pythonanywhere.com/login/"


def open_console(url: str) -> None:
    """Log in and load a PA console URL headlessly to trigger console startup."""
    username = os.environ["API_USER"]
    password = os.environ["PA_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(LOGIN_URL)
        page.locator("#id_auth-username").fill(username)
        page.locator("#id_auth-password").fill(password)
        page.locator("#id_next").click()
        page.wait_for_load_state("networkidle")

        if "/login/" in page.url:
            raise RuntimeError("PythonAnywhere login failed; check PA_PASSWORD secret.")

        page.goto(url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)
        browser.close()
