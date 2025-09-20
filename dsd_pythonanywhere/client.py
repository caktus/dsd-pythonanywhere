import logging
import os
import re
import time
import webbrowser

import requests
from pythonanywhere_core.base import get_api_endpoint
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


PROMPT_REGEX = re.compile(r"\x1b\[1;32m\$ \x1b\[0;0m([^\r\n]*)")


class APIClient:
    """PythonAnywhere API client."""

    def __init__(self, username: str):
        self.username = username
        self.token = os.getenv("API_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Token {self.token}"})
        self.session.mount("https://", HTTPAdapter(max_retries=3))
        self.console_url: str = ""

    @property
    def _hostname(self) -> str:
        return os.getenv(
            "PYTHONANYWHERE_SITE",
            "www." + os.environ.get("PYTHONANYWHERE_DOMAIN", "pythonanywhere.com"),
        )

    def _base_url(self, flavor: str) -> str:
        return get_api_endpoint(username=self.username, flavor=flavor).rstrip("/")

    def _parse_last_command_output(self, output: str) -> tuple[str, str]:
        """Extract the last command run and the output from a block of console output.

        The output contains ANSI escape sequences and follows a specific pattern. Look
        for the pattern: time ~ $ command\r\n followed by output

        Returns: (command, command_output)
        """

        # Split on the prompt pattern that includes the green $ and command
        # Pattern: \x1b[1;32m$ \x1b[0;0m followed by command and \r\n
        parts = PROMPT_REGEX.split(output)

        command = None
        command_output = None
        if len(parts) >= 3:
            # Look for the last non-empty command by going backwards through the parts
            # Step by 2, going backwards
            for i in range(len(parts) - 2, -1, -2):
                if i >= 0 and parts[i].strip():
                    command = parts[i].strip()
                    # Get the output that follows this command (next part)
                    if i + 1 < len(parts):
                        raw_output = parts[i + 1]

                        # Clean up the output part - remove ANSI escape sequences and control chars
                        clean_output = re.sub(
                            r"\x1b\[\?2004l\r", "", raw_output
                        )  # Remove terminal mode
                        clean_output = re.sub(
                            r"\x1b\[\?2004h.*$", "", clean_output
                        )  # Remove trailing terminal setup
                        clean_output = clean_output.strip("\r\n")

                        command_output = clean_output
                    break

        return command, command_output

    def _wait_for_console_ready(self, console_url: str, browser_console_url: str) -> None:
        """Wait for console to be ready by polling with a test command."""
        max_retries = 30
        browser_opened = False
        test_command = "echo hello"
        expected_output = "hello"

        for attempt in range(max_retries):
            logger.debug(f"Attempt {attempt}: checking if console is ready")

            response = self.request(
                method="POST",
                url=f"{console_url}/send_input/",
                json={"input": f"\n{test_command}\n"},
                raise_for_status=False,
            )

            if response.status_code == 412:
                # Console not started, open in browser if we haven't already
                if not browser_opened:
                    logger.debug("Console not started, opening browser...")
                    webbrowser.open(f"https://{self._hostname}{browser_console_url}")
                    browser_opened = True
                time.sleep(2)
                continue

            if not response.ok:
                time.sleep(2)
                continue

            # Check if our test command executed successfully
            output_response = self.request(
                method="GET", url=f"{console_url}/get_latest_output/", raise_for_status=False
            )

            if output_response.ok:
                output = output_response.json()["output"]
                resp_cmd, resp_output = self._parse_last_command_output(output)

                if resp_cmd == test_command and resp_output.strip() == expected_output:
                    logger.debug("Console is ready")
                    return

            time.sleep(2)

        raise RuntimeError("Console did not become ready after waiting.")

    def request(self, method: str, url: str, *args, **kwargs):
        """Makes PythonAnywhere API request."""
        raise_for_status: bool = kwargs.pop("raise_for_status", True)
        url = url.rstrip("/")
        response = self.session.request(method=method, url=f"{url}/", *args, **kwargs)
        try:
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            try:
                error_data = e.response.json() if e.response is not None else None
            except requests.exceptions.JSONDecodeError:
                error_data = None
            status_code = getattr(e.response, "status_code", None)
            logger.debug(f"API error {status_code=} {error_data=}", extra={"response": e.response})
            if raise_for_status:
                raise
        logger.debug(f"API response: {response.status_code} {response.text}")
        return response

    def get_active_console_url(self) -> str:
        """Return URL to an active PythonAnywhere bash console."""
        base_url = self._base_url("consoles")

        # Get existing consoles or create a new bash console
        consoles = self.request(method="GET", url=base_url).json()
        bash_console = None
        for console in consoles:
            if console.get("executable") == "bash":
                bash_console = console
                break

        if not bash_console:
            logger.debug("No active bash console found, starting a new one...")
            bash_console = self.request(
                method="POST", url=base_url, json={"executable": "bash"}
            ).json()

        console_url = f"{base_url}/{bash_console['id']}"
        # Wait for console to be ready by testing with a simple command
        self._wait_for_console_ready(console_url, bash_console.get("console_url", ""))
        return console_url

    def run_command(self, command: str) -> str:
        """Run a command in an active bash console and return the output."""
        console_url = self.get_active_console_url()
        if not console_url:
            raise RuntimeError("No active bash console found")
        response = self.request(
            method="POST", url=f"{console_url}/send_input/", json={"input": f"{command}\n"}
        )
        output = ""
        if response.ok:
            output = self.session.get(f"{console_url}/get_latest_output/").json()["output"]
            resp_cmd, resp_output = self._parse_last_command_output(output)
        return resp_cmd, resp_output
