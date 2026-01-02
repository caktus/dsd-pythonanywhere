import logging
import os
import re
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import requests
from django_simple_deploy.management.commands.utils import plugin_utils
from pythonanywhere_core.base import get_api_endpoint
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


def log_message(message: str, level: int = logging.INFO, **kwargs) -> None:
    """Helper function to log messages to both logger and plugin_utils output.

    Args:
        message: The message to log
        level: The logging level (default: DEBUG)
        **kwargs: Additional keyword arguments for the logger
    """
    logger.log(level, message, **kwargs)
    if plugin_utils.dsd_config.stdout is not None and level >= logging.INFO:
        plugin_utils.write_output(f"  {message}")


@dataclass
class CommandResult:
    """Result of running a command in the console."""

    command: str
    output: str


class CommandRun:
    """Handles parsing and analysis of console command output."""

    # Regex pattern to match console prompts: "HH:MM ~ $"
    PROMPT_PATTERN = re.compile(r"\d{2}:\d{2} ~.*\$")
    # Regex pattern to match empty prompts (command finished): "HH:MM ~ $ " (with optional whitespace)
    EMPTY_PROMPT_PATTERN = re.compile(r"\d{2}:\d{2} ~[^$]*\$\s*$")
    # Regex pattern to match ANSI escape codes for cleaning
    # Matches SGR sequences (\x1b[...m), bracketed paste mode (\x1b[?2004h/l), and other CSI sequences
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

    def __init__(self, raw_output: str):
        self.raw_output = raw_output
        self.lines = raw_output.splitlines()

    def find_most_recent_prompt_line(self, expected_command: str | None = None) -> int | None:
        """Find the most recent prompt line in console output.

        Walks backwards through lines to find the most recent line containing a
        prompt pattern. Optionally filters for prompts containing a specific
        command.

        Args:
            expected_command: If provided, return most recent prompt containing
                              this command.

        Returns: Line index if found, None otherwise
        """
        for i in range(len(self.lines) - 1, -1, -1):
            line = self.lines[i]
            if self.PROMPT_PATTERN.search(line) and (
                expected_command is None or expected_command in line
            ):
                return i
        return None

    def extract_command_output(self, expected_command: str) -> str | None:
        """Extract output for a specific command from console lines.

        Find our command, then collect output that appears after it until the
        next prompt.
        """
        command_line_index = self.find_most_recent_prompt_line(expected_command=expected_command)
        if command_line_index is None:
            return None

        # Now collect output lines that appear AFTER the command line
        output_lines = []
        for i in range(command_line_index + 1, len(self.lines)):
            line = self.lines[i]

            # Stop when we hit the next prompt (indicating command finished)
            if self.PROMPT_PATTERN.search(line):
                break

            # Skip terminal control sequences that don't contain actual output
            if line.strip() and not line.strip().startswith("\x1b[?2004"):
                output_lines.append(line)

        return "\n".join(output_lines).strip()

    def is_command_finished(self) -> bool:
        """Check if the most recent command has finished executing.

        Returns True if the most recent prompt is empty (command finished),
        False if it contains command text (still running).
        """
        recent_prompt_index = self.find_most_recent_prompt_line()
        if recent_prompt_index is None:
            return False

        line = self.lines[recent_prompt_index]
        # Clean ANSI escape codes to check if it's an empty prompt
        clean_line = self.ANSI_ESCAPE_PATTERN.sub("", line)

        # Check if this is an empty prompt (command finished)
        return bool(self.EMPTY_PROMPT_PATTERN.search(clean_line))


class Console:
    """Handles API interactions with a PythonAnywhere console.

    Since PythonAnywhere doesn't offer SSH access for free accounts, we interact
    with a bash console via the API. This class manages sending commands,
    polling for output, and determining when commands have finished. It's a bit
    clunky, but it works well enough for basic tasks.

    See https://help.pythonanywhere.com/pages/API/#consoles for more details.
    """

    def __init__(self, bash_console: dict, api_client: "PythonAnywhereClient"):
        # Full console info returned from Consoles API endpoint
        self.bash_console = bash_console
        self.api_client = api_client
        # Derive console URLs from bash_console data
        base_url = api_client._base_url("consoles")
        self.api_url = f"{base_url}/{bash_console['id']}"
        self.browser_url = self.api_url.replace("/api/v0/", "/")

    def send_input(self, input_text: str) -> requests.Response:
        """Send input to the console.

        Args:
            input_text: The input text to send to the console

        Returns:
            The requests.Response object from the API call
        """
        return self.api_client.request(
            method="POST",
            url=f"{self.api_url}/send_input/",
            json={"input": input_text},
            raise_for_status=False,
        )

    def get_latest_output(self) -> CommandRun | None:
        """Get the latest console output as a CommandRun object.

        Returns CommandRun object for parsing, or None if request failed.
        """
        response = self.api_client.request(
            method="GET", url=f"{self.api_url}/get_latest_output/", raise_for_status=False
        )
        if response.ok:
            raw_output = response.json()["output"]
            return CommandRun(raw_output)
        return None

    def wait_for_command_completion(
        self, expected_command: str, max_retries: int = 60
    ) -> CommandResult:
        """Wait for a command to complete by polling console output.

        Returns: CommandResult with command and output when command is finished
        """
        for attempt in range(max_retries):
            log_message(
                f"  Polling attempt {attempt + 1}: waiting for command '{expected_command}' to complete"
            )

            try:
                command_run = self.get_latest_output()
                if command_run:
                    # First check if our command appears in the output (was echoed back)
                    command_visible = command_run.find_most_recent_prompt_line(
                        expected_command=expected_command
                    )
                    if command_visible is None:
                        log_message("Command not yet visible in output, waiting...")
                        time.sleep(6)
                        continue

                    # Command is visible, now check if it finished (empty prompt after)
                    if command_run.is_command_finished():
                        command_output = command_run.extract_command_output(expected_command)
                        if command_output is not None:
                            log_message(f"Command '{expected_command}' completed")
                            return CommandResult(expected_command, command_output)

            except Exception as e:
                log_message(f"Error polling console output: {e}")

            log_message("Command not finished yet, sleeping before next poll...")
            time.sleep(6)

        raise RuntimeError(
            f"Command '{expected_command}' did not complete after {max_retries} attempts"
        )

    def wait_for_ready(self) -> None:
        """Wait for console to be ready by polling with a test command.

        Starting a new console process can take some time. We poll by sending a
        simple command ("echo hello") and checking the output until we see
        "hello". If a console is not yet started, we open it in the browser to
        trigger startup.
        """
        max_retries = 30
        browser_opened = False
        test_command = "echo hello"

        for attempt in range(max_retries):
            log_message(f"  Attempt {attempt}: checking if console is ready")

            # Send the test command input (with newline before to clear any partial input)
            response = self.send_input(f"\n{test_command}\n")

            if not response.ok:
                if response.status_code == 412:
                    # Console not started, open in browser if we haven't already
                    if not browser_opened:
                        log_message("  Console not started, opening browser...")
                        webbrowser.open(self.browser_url)
                        browser_opened = True
                    # Wait for browser opening to trigger startup
                    time.sleep(5)
                    continue

                time.sleep(2)
                continue

            # Check if the test command completed
            try:
                result = self.wait_for_command_completion(test_command, max_retries=5)
                if result.output.strip() == "hello":
                    log_message("  Console is ready")
                    return
            except RuntimeError:
                # Command didn't complete, continue trying
                pass

            time.sleep(5)

        raise RuntimeError("Console did not become ready after waiting.")

    def run_command(self, command: str) -> str:
        """Run a command and return its output.

        Args:
            command: The command string to run in the console

        Returns:
            The command output as a string, or empty string if command failed
        """
        response = self.send_input(f"{command}\n")
        if not response.ok:
            return ""

        result = self.wait_for_command_completion(command)
        return result.output


class PythonAnywhereClient:
    """Client for interacting with the PythonAnywhere API, including console and webapp management."""

    def __init__(self, username: str):
        self.username = username
        self.token = os.getenv("API_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Token {self.token}"})
        self.session.mount("https://", HTTPAdapter(max_retries=3))
        # Initialize webapp for this user's domain
        self.domain_name = f"{username}.{self._pythonanywhere_domain}"

        # CRITICAL: Set LOGNAME before importing Webapp, which has class
        # variables (username, files_url, webapps_url) that are computed at
        # import time using getpass.getuser(), which reads LOGNAME. If we import
        # Webapp at the module level, those class variables will be set with the
        # wrong username. By setting LOGNAME first, then doing a lazy import
        # here, we ensure Webapp uses the correct username for all API calls.
        if self.username and self.username != os.getenv("LOGNAME"):
            os.environ["LOGNAME"] = self.username

        # Lazy import after LOGNAME is set so class variables use correct username
        from pythonanywhere_core.webapp import Webapp

        self.webapp = Webapp(domain=self.domain_name)
        self.webapp.username = self.username

    @property
    def _pythonanywhere_domain(self) -> str:
        """Get the PythonAnywhere domain (e.g., 'pythonanywhere.com')."""
        return os.getenv("PYTHONANYWHERE_DOMAIN", "pythonanywhere.com")

    @property
    def _hostname(self) -> str:
        """Get the PythonAnywhere API hostname (e.g., 'www.pythonanywhere.com')."""
        return os.getenv("PYTHONANYWHERE_SITE", f"www.{self._pythonanywhere_domain}")

    def _base_url(self, flavor: str) -> str:
        """Construct the base URL for a specific API endpoint flavor.

        Args:
            flavor: The API endpoint type (e.g., "consoles", "files", "tasks")

        Returns:
            The complete base URL for the specified API endpoint, e.g.:
            https://{hostname}/api/v0/user/{username}/{flavor}
        """
        return get_api_endpoint(username=self.username, flavor=flavor).rstrip("/")

    def request(self, method: str, url: str, **kwargs):
        """Makes PythonAnywhere API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to make the request to
            **kwargs: Additional keyword arguments for requests.request

            Optionally, you can pass 'raise_for_status' (bool) to control
            whether to raise an exception on HTTP error responses (default True).

        Returns:
            The requests.Response object from the API call.
        """
        raise_for_status: bool = kwargs.pop("raise_for_status", True)
        # Always ensure URL does not end with a slash
        url = url.rstrip("/")
        response = self.session.request(method=method, url=f"{url}/", **kwargs)
        try:
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            try:
                error_data = e.response.json() if e.response is not None else None
            except requests.exceptions.JSONDecodeError:
                error_data = None
            status_code = getattr(e.response, "status_code", None)
            log_message(f"API error {status_code=} {error_data=}", extra={"response": e.response})
            if raise_for_status:
                raise
        log_message(f"API response: {response.status_code} {response.text}", level=logging.DEBUG)
        return response

    # --- Console management methods ---

    def get_active_console(self) -> Console:
        """Return an active PythonAnywhere bash console."""
        base_url = self._base_url("consoles")

        # Get existing consoles or create a new bash console
        consoles = self.request(method="GET", url=base_url).json()
        bash_console = None
        for console in consoles:
            if console.get("executable") == "bash":
                bash_console = console
                break

        # Create a new bash console if none exists
        if not bash_console:
            log_message("No active bash console found, starting a new one...")
            bash_console = self.request(
                method="POST", url=base_url, json={"executable": "bash"}
            ).json()

        console = Console(bash_console=bash_console, api_client=self)
        # Wait for console to be ready by testing with a simple command
        console.wait_for_ready()
        return console

    def run_command(self, command: str) -> str:
        """Run a command in an active bash console and return the output."""
        console = self.get_active_console()
        if not console:
            raise RuntimeError("No active bash console found")

        return console.run_command(command)

    # --- Webapp management methods ---

    def webapp_exists(self) -> bool:
        """Check if a web app already exists for this domain.

        Returns:
            True if a webapp exists, False otherwise
        """
        webapps = self.webapp.list_webapps()
        return any(app.get("domain_name") == self.domain_name for app in webapps)

    def create_webapp(
        self,
        python_version: str,
        virtualenv_path: Path,
        project_path: Path,
        nuke: bool = False,
    ) -> None:
        """Create a new web app on PythonAnywhere.

        Args:
            python_version: Python version (e.g., "3.13")
            virtualenv_path: Path to the virtual environment
            project_path: Path to the Django project
            nuke: If True, delete existing webapp before creating
        """
        self.webapp.sanity_checks(nuke=nuke)
        self.webapp.create(
            python_version=python_version,
            virtualenv_path=virtualenv_path,
            project_path=project_path,
            nuke=nuke,
        )

    def create_webapp_if_not_exists(
        self, python_version: str, virtualenv_path: Path, project_path: Path
    ) -> None:
        """Create a webapp if it doesn't exist.

        Args:
            python_version: Python version (e.g., "3.13")
            virtualenv_path: Path to the virtual environment
            project_path: Path to the Django project
        """
        if not self.webapp_exists():
            self.create_webapp(
                python_version=python_version,
                virtualenv_path=virtualenv_path,
                project_path=project_path,
                nuke=False,
            )
            log_message("Configuring static file mappings...")
            self.webapp.add_default_static_files_mappings(project_path=project_path)
            log_message("Static file mappings configured")
        else:
            log_message(f"Webapp {self.domain_name} already exists, skipping creation")

    def reload_webapp(self) -> None:
        """Reload the web app to apply changes."""
        log_message(f"Reloading webapp {self.domain_name}...")
        self.webapp.reload()
        log_message("Webapp reloaded successfully")
