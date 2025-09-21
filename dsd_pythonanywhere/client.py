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
                            r"\x1b\[\?2004[lh]\r?", "", raw_output
                        )  # Remove terminal mode sequences
                        # Remove the trailing prompt/terminal setup but preserve the actual output
                        clean_output = re.sub(
                            r"\x1b\[0;0m\d{2}:\d{2} ~.*$", "", clean_output
                        )  # Remove trailing prompt
                        clean_output = clean_output.strip("\r\n")

                        command_output = clean_output
                    break

        return command, command_output

    def _parse_specific_command_output(self, output: str, target_command: str) -> tuple[str, str]:
        """Extract a specific command and its output from console output.

        Look for the target_command specifically in the console history and return the output
        from the MOST RECENT execution (last occurrence).

        Returns: (command, command_output) if found, (None, None) if not found
        """
        # Split on the prompt pattern that includes the green $ and command
        parts = PROMPT_REGEX.split(output)

        # Look through all commands to find our target, but keep track of the LAST match
        last_command = None
        last_output = None

        for i in range(1, len(parts), 2):  # Commands are in odd-indexed parts
            if i < len(parts) and parts[i].strip() == target_command:
                command = parts[i].strip()

                # Get the output that follows this command (next part)
                if i + 1 < len(parts):
                    raw_output = parts[i + 1]

                    # Clean up the output part - remove ANSI escape sequences and control chars
                    clean_output = re.sub(
                        r"\x1b\[\?2004[lh]\r?", "", raw_output
                    )  # Remove terminal mode sequences
                    # Remove the trailing prompt/terminal setup but preserve the actual output
                    clean_output = re.sub(
                        r"\x1b\[0;0m\d{2}:\d{2} ~.*$", "", clean_output
                    )  # Remove trailing prompt
                    clean_output = clean_output.strip("\r\n")

                    # Keep this as the most recent match (don't return immediately)
                    last_command = command
                    last_output = clean_output

        return last_command, last_output

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
                resp_cmd, resp_output = self.get_console_output(console_url, output_response)

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

    def get_console_output(self, console_url: str, output_response=None) -> tuple[str, str]:
        """Get the latest output from console and parse the last command."""
        if output_response is None:
            output = self.session.get(f"{console_url}/get_latest_output/").json()["output"]
        else:
            output = output_response.json()["output"]
        return self._parse_last_command_output(output)

    def _wait_for_command_completion(
        self, console_url: str, expected_command: str, max_retries: int = 30
    ) -> tuple[str, str]:
        """Wait for a command to complete by polling console output until we see a prompt.

        Returns: (command, command_output) when a new prompt appears (indicating command finished)
        """
        for attempt in range(max_retries):
            logger.debug(
                f"Polling attempt {attempt + 1}: waiting for command '{expected_command}' to complete"
            )

            try:
                output_response = self.request(
                    method="GET", url=f"{console_url}/get_latest_output/", raise_for_status=False
                )

                if output_response.ok:
                    output = output_response.json()["output"]

                    # Check if the output ends with a prompt (indicating the command finished and console is ready)
                    # The prompt pattern should appear at the end, followed by possible whitespace/control chars
                    # Look for: timestamp ~ $ at the end (allowing for terminal control sequences)
                    prompt_at_end = re.search(r"\d{2}:\d{2} ~[^$]*\$ [^$]*$", output)

                    if prompt_at_end:
                        # Instead of parsing the last command, look for our specific command
                        resp_cmd, resp_output = self._parse_specific_command_output(
                            output, expected_command
                        )

                        # Check if we found our specific command
                        if resp_cmd and resp_cmd == expected_command:
                            logger.debug(
                                f"Command completed (found: '{resp_cmd}', expected: '{expected_command}') with prompt ready"
                            )
                            return resp_cmd, resp_output

            except Exception as e:
                logger.debug(f"Error polling console output: {e}")

            time.sleep(1)  # Wait before next poll

        raise RuntimeError(
            f"Command '{expected_command}' did not complete after {max_retries} attempts"
        )

    def run_command(self, command: str) -> str:
        """Run a command in an active bash console and return the output."""
        console_url = self.get_active_console_url()
        if not console_url:
            raise RuntimeError("No active bash console found")
        response = self.request(
            method="POST", url=f"{console_url}/send_input/", json={"input": f"{command}\n"}
        )
        if response.ok:
            # Wait for the command to complete by polling the output
            resp_cmd, resp_output = self._wait_for_command_completion(console_url, command)
            return resp_output
        return ""
