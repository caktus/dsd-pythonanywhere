import pytest

from dsd_pythonanywhere.client import APIClient, CommandResult, CommandRun, Console


@pytest.fixture
def mock_api_client(mocker):
    """APIClient instance with mocked request method."""
    mocker.patch.dict("os.environ", {"API_TOKEN": "test_token_12345"})
    client = APIClient(username="testuser")
    mocker.patch.object(client, "request")
    return client


@pytest.fixture
def bash_console():
    """Sample bash console data from PythonAnywhere API."""
    return {
        "id": 12345,
        "user": "testuser",
        "executable": "bash",
        "arguments": "",
        "working_directory": None,
        "name": None,
        "console_url": "https://www.pythonanywhere.com/user/testuser/consoles/12345/",
        "console_frame_url": "https://www.pythonanywhere.com/user/testuser/consoles/12345/frame/",
    }


@pytest.fixture
def console(bash_console: dict, mock_api_client):
    """Console instance for testing."""
    return Console(bash_console=bash_console, api_client=mock_api_client)


def test_console_init(bash_console: dict, mock_api_client):
    """Console initializes with correct URLs."""
    console = Console(bash_console=bash_console, api_client=mock_api_client)
    assert console.bash_console == bash_console
    assert console.api_client == mock_api_client
    assert console.api_url == "https://www.pythonanywhere.com/api/v0/user/testuser/consoles/12345"
    assert console.browser_url == "https://www.pythonanywhere.com/user/testuser/consoles/12345"


def test_send_input(console: Console, mock_api_client):
    """send_input makes POST request with input text."""
    mock_response = mock_api_client.request.return_value
    result = console.send_input("ls -la")

    mock_api_client.request.assert_called_once_with(
        method="POST",
        url="https://www.pythonanywhere.com/api/v0/user/testuser/consoles/12345/send_input/",
        json={"input": "ls -la"},
        raise_for_status=False,
    )
    assert result == mock_response


def test_get_latest_output_success(console: Console, mock_api_client):
    """get_latest_output returns CommandRun when request succeeds."""
    mock_response = mock_api_client.request.return_value
    mock_response.ok = True
    mock_response.json.return_value = {"output": "test output\n"}

    result = console.get_latest_output()
    assert isinstance(result, CommandRun)
    assert result.raw_output == "test output\n"


def test_get_latest_output_failure(console: Console, mock_api_client):
    """get_latest_output returns None when request fails."""
    mock_response = mock_api_client.request.return_value
    mock_response.ok = False

    result = console.get_latest_output()
    assert result is None


def test_wait_for_command_completion_success(console, mocker):
    """wait_for_command_completion returns CommandResult when command finishes."""
    # Mock get_latest_output to return a finished command
    mock_command_run = mocker.MagicMock()
    mock_command_run.is_command_finished.return_value = True
    mock_command_run.extract_command_output.return_value = "output text"
    mocker.patch.object(console, "get_latest_output", return_value=mock_command_run)

    result = console.wait_for_command_completion("echo test", max_retries=5)
    assert isinstance(result, CommandResult)
    assert result.command == "echo test"
    assert result.output == "output text"


def test_wait_for_command_completion_timeout(console, mocker):
    """wait_for_command_completion raises RuntimeError on timeout."""
    # Mock get_latest_output to return a command that never finishes
    mock_command_run = mocker.MagicMock()
    mock_command_run.is_command_finished.return_value = False
    mocker.patch.object(console, "get_latest_output", return_value=mock_command_run)
    mocker.patch("dsd_pythonanywhere.client.time.sleep")  # Speed up test

    with pytest.raises(RuntimeError, match="did not complete after 3 attempts"):
        console.wait_for_command_completion("echo test", max_retries=3)


def test_wait_for_command_completion_handles_exceptions(console, mocker):
    """wait_for_command_completion continues on exceptions."""
    # First call raises exception, second call succeeds
    mock_command_run = mocker.MagicMock()
    mock_command_run.is_command_finished.return_value = True
    mock_command_run.extract_command_output.return_value = "output"
    mocker.patch.object(
        console,
        "get_latest_output",
        side_effect=[Exception("network error"), mock_command_run],
    )
    mocker.patch("dsd_pythonanywhere.client.time.sleep")

    result = console.wait_for_command_completion("echo test", max_retries=5)
    assert result.output == "output"
