import logging
import os
import time
import webbrowser

import requests
from pythonanywhere_core.base import get_api_endpoint
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


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
        """Return URL to an active PythonAnywhere bash console.

        If no active bash console exists, attempt to start a new one. See
        https://help.pythonanywhere.com/pages/API/#apiv0userusernameconsoles for
        details.

        API response looks like:
            [{'id': 42068374, 'user': 'myuser', 'executable': 'bash',
            'arguments': '', 'working_directory': None, 'name': 'Bash console
            42068374', 'console_url': '/user/myuser/consoles/42068374/',
            'console_frame_url': '/user/myuser/consoles/42068374/frame/'}]
        """
        base_url = self._base_url("consoles")
        consoles = self.request(method="GET", url=base_url).json()
        bash_console = {}
        for console in consoles:
            if console.get("executable") == "bash":
                bash_console = console
                break
        if not bash_console:
            # Try to start a new bash console
            logger.debug("No active bash console found, starting a new one...")
            bash_console = self.request(
                method="POST", url=base_url, json={"executable": "bash"}
            ).json()
        logger.debug(f"Found bash console: {bash_console}")
        bash_console_url = f"{base_url}/{bash_console['id']}"

        # Run test command to see if it's active
        max_retries = 30  # Wait up to 30 seconds
        browser_opened = False
        for attempt in range(max_retries):
            logger.debug(f"Attempt {attempt}: checking if console is active")
            # Attempt to send input to the console
            response = self.request(
                method="POST",
                url=f"{bash_console_url}/send_input/",
                json={"input": "whoami\n"},
                raise_for_status=False,
            )
            if response.status_code == 412:
                # Console not yet started, so we must open it in a browser per the API docs
                if not browser_opened:
                    logger.debug("Console not yet started, opening browser...")
                    webbrowser.open(f"https://{self._hostname}{bash_console['console_url']}")
                    browser_opened = True
                logger.debug("Console not yet started, waiting...")
                time.sleep(1)
                continue
            else:
                # Successfully sent input, console is active
                logger.debug("Console is active.")
                break
        else:
            logger.error("Console did not become ready after waiting.")
            raise RuntimeError("Console did not become ready after waiting.")

        return bash_console_url

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
        return output
