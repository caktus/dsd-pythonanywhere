"""PythonAnywhere-specific e2e test helpers: headless console login and account reset.

Both entry points expect PYTHONPATH to include the plugin's tests/ dir, so
this module resolves as the top-level package "e2e_tests.pa_admin" -- see
.github/workflows/e2e_pythonanywhere.yaml and scripts/run_e2e_local.sh.
"""

import os

from playwright.sync_api import sync_playwright

from . import utils as platform_utils

LOGIN_URL = "https://www.pythonanywhere.com/login/"


def open_console(url: str) -> None:
    """Log in and load a PA console URL headlessly to trigger console startup.

    Loading the console URL triggers PA's client-side JS to open a websocket
    and spawn the actual bash console process server-side -- something the API
    alone cannot do. Resolved via
    DSD_PYTHONANYWHERE_CONSOLE_OPENER=e2e_tests.pa_admin:open_console
    (see dsd_pythonanywhere.client._get_console_opener).
    """
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


def reset_account() -> None:
    """Wipe PythonAnywhere account state so each e2e run starts clean.

    setup.sh skips re-cloning/re-creating the venv if they already exist, so a
    dirty account from a prior run won't self-clean; call this before (and
    after, via `if: always()`) each e2e run. Requires API_USER, API_TOKEN, and
    DEMO_REPO_NAME environment variables.
    """
    repo_name = os.environ["DEMO_REPO_NAME"]
    client = platform_utils.get_client()

    if client.webapp_exists():
        print("Deleting existing webapp...")
        client.webapp.delete()

    print(f"Removing ~/{repo_name} and ~/venv...")
    client.run_command(f"rm -rf ~/{repo_name} ~/venv")


if __name__ == "__main__":
    reset_account()
