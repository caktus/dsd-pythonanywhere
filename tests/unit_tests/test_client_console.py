import pytest

from dsd_pythonanywhere.client import CommandResult, CommandRun, Console, PythonAnywhereClient


@pytest.fixture
def mock_api_client(mocker):
    """APIClient instance with mocked request method."""
    mocker.patch.dict("os.environ", {"API_TOKEN": "test_token_12345"})
    client = PythonAnywhereClient(username="testuser")
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


def test_wait_for_command_completion_scrolled_off_buffer(console, mocker):
    """Command completing after its prompt line scrolls out of the output buffer.

    Long-running commands produce enough output to push the original echo line
    out of the console buffer.  The first poll sees the command; subsequent
    polls no longer see it but do see an empty prompt (finished).
    """
    # First poll: command visible, not yet finished
    run1 = mocker.MagicMock()
    run1.find_most_recent_prompt_line.return_value = 0  # command still in buffer
    run1.is_command_finished.return_value = False

    # Second poll: command scrolled off buffer (returns None), but prompt is empty (finished)
    run2 = mocker.MagicMock()
    run2.find_most_recent_prompt_line.return_value = None  # scrolled off
    run2.is_command_finished.return_value = True
    run2.extract_command_output.return_value = None  # can't find it anymore

    mocker.patch.object(console, "get_latest_output", side_effect=[run1, run2])
    mocker.patch("dsd_pythonanywhere.client.time.sleep")

    result = console.wait_for_command_completion("long-command", max_retries=5)
    assert result.command == "long-command"
    assert result.output == ""


def test_wait_for_command_completion_debug_polling(console, mocker):
    """DEBUG_POLLING env var causes raw output to be logged."""
    mock_command_run = mocker.MagicMock()
    mock_command_run.raw_output = "raw console output"
    mock_command_run.is_command_finished.return_value = True
    mock_command_run.extract_command_output.return_value = "output"
    mocker.patch.object(console, "get_latest_output", return_value=mock_command_run)
    mocker.patch("dsd_pythonanywhere.client.time.sleep")
    mock_log = mocker.patch("dsd_pythonanywhere.client.log_message")
    mocker.patch.dict("os.environ", {"DEBUG_POLLING": "1"})

    console.wait_for_command_completion("echo test", max_retries=1)

    debug_calls = [c for c in mock_log.call_args_list if "DEBUG_POLLING" in str(c)]
    assert debug_calls, "Expected DEBUG_POLLING log message"
    assert "raw console output" in str(debug_calls[0])


def test_run_command_returns_output_on_success(console, mocker):
    """run_command strips the exit-status marker and returns the real output."""
    mocker.patch.object(console, "send_input", return_value=mocker.Mock(ok=True))
    mock_result = CommandResult(command="ls", output="foo\nbar\nDSD_EXIT_STATUS:0")
    mocker.patch.object(console, "wait_for_command_completion", return_value=mock_result)

    output = console.run_command("ls")

    assert output == "foo\nbar"


def test_run_command_raises_when_send_fails(console, mocker):
    """run_command raises rather than silently returning an empty string."""
    mocker.patch.object(console, "send_input", return_value=mocker.Mock(ok=False))

    with pytest.raises(RuntimeError, match="Failed to send command"):
        console.run_command("ls")


def test_run_command_raises_on_nonzero_exit_status(console, mocker):
    """run_command raises when the command's own exit status is non-zero."""
    mocker.patch.object(console, "send_input", return_value=mocker.Mock(ok=True))
    mock_result = CommandResult(command="false", output="some error text\nDSD_EXIT_STATUS:1")
    mocker.patch.object(console, "wait_for_command_completion", return_value=mock_result)

    with pytest.raises(RuntimeError, match="exited with status 1"):
        console.run_command("false")


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
