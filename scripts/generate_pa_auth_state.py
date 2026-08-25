"""One-time, interactive helper to (re)generate the PA_AUTH_STATE secret.

Run this locally with a real browser whenever the saved PythonAnywhere login
session used by tests/e2e_tests/headless_console_opener.py expires. Upload the
resulting file's contents as the PA_AUTH_STATE GitHub Actions secret.

Usage: uv run python scripts/generate_pa_auth_state.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path("pa_auth_state.json")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.pythonanywhere.com/login/")
        input("Log in manually in the opened browser, then press Enter here...")
        page.context.storage_state(path=str(OUTPUT_PATH))
        browser.close()
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
