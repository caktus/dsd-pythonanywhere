import logging
import os
import re
import time
import webbrowser
from dataclasses import dataclass

import requests
from pythonanywhere_core.base import get_api_endpoint
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of running a command in the console."""

    command: str
    output: str


class APIClient:
    """PythonAnywhere API client."""

    # Regex pattern to match console prompts: "HH:MM ~ $"
    PROMPT_PATTERN = re.compile(r"\d{2}:\d{2} ~.*\$")
    # Regex pattern to match empty prompts (command finished): "HH:MM ~ $ " (with optional whitespace)
    EMPTY_PROMPT_PATTERN = re.compile(r"\d{2}:\d{2} ~[^$]*\$\s*$")
    # Regex pattern to match ANSI escape codes for cleaning
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

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

    def _wait_for_console_ready(self, console_url: str, browser_console_url: str) -> None:
        """Wait for console to be ready by polling with a test command."""
        max_retries = 30
        browser_opened = False
        test_command = "echo hello"

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

            # Check if the command completed
            try:
                result = self._wait_for_command_completion(console_url, test_command, max_retries=5)
                if result.output.strip() == "hello":
                    logger.debug("Console is ready")
                    return
            except RuntimeError:
                # Command didn't complete, continue trying
                pass

            time.sleep(2)

        raise RuntimeError("Console did not become ready after waiting.")

    def _wait_for_command_completion(
        self, console_url: str, expected_command: str, max_retries: int = 30
    ) -> CommandResult:
        """Wait for a command to complete by polling console output until we see a prompt.

        Uses a simple approach: split output into lines and walk backwards to find either:
        1. Our command prompt (still running)
        2. An empty prompt (finished)

        Returns: CommandResult with command and output when command is finished
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
                    lines = output.splitlines()

                    # Walk backwards through lines to find the most recent prompt
                    for i in range(len(lines) - 1, -1, -1):
                        line = lines[i]

                        # Look for a prompt pattern: timestamp ~ $
                        if self.PROMPT_PATTERN.search(line):
                            # Clean ANSI escape codes to check if it's an empty prompt
                            # Remove ANSI escape sequences like \x1b[0;0m, \x1b[1;32m, etc.
                            clean_line = self.ANSI_ESCAPE_PATTERN.sub("", line)

                            # Check if this is an empty prompt (command finished)
                            # Look for pattern: timestamp ~ $ (with possible whitespace/control chars after)
                            if self.EMPTY_PROMPT_PATTERN.search(clean_line):
                                # Command finished, extract output
                                command_output = self._extract_command_output(
                                    lines, expected_command
                                )
                                if command_output is not None:
                                    logger.debug(f"Command '{expected_command}' completed")
                                    return CommandResult(expected_command, command_output)
                            else:
                                # Prompt has command text, still running
                                logger.debug(f"Command still running: {repr(clean_line)}")
                                break

            except Exception as e:
                logger.debug(f"Error polling console output: {e}")

            time.sleep(1)  # Wait before next poll

        raise RuntimeError(
            f"Command '{expected_command}' did not complete after {max_retries} attempts"
        )

    def _extract_command_output(self, lines: list[str], expected_command: str) -> str | None:
        """Extract output for a specific command from console lines.

        Find our command, then collect output that appears after it until the next prompt.
        """
        command_line_index = None

        # First, find our command line (walking backwards to get the most recent)
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            if expected_command in line and self.PROMPT_PATTERN.search(line):
                command_line_index = i
                break

        if command_line_index is None:
            return None

        # Now collect output lines that appear AFTER the command line
        output_lines = []
        for i in range(command_line_index + 1, len(lines)):
            line = lines[i]

            # Stop when we hit the next prompt (indicating command finished)
            if self.PROMPT_PATTERN.search(line):
                break

            # Skip terminal control sequences that don't contain actual output
            if line.strip() and not line.strip().startswith("\x1b[?2004"):
                output_lines.append(line)

        return "\n".join(output_lines).strip()

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

        # Send the command
        response = self.request(
            method="POST", url=f"{console_url}/send_input/", json={"input": f"{command}\n"}
        )
        if response.ok:
            # Wait for the command to complete by polling the output
            result = self._wait_for_command_completion(console_url, command)
            return result.output
        return ""
