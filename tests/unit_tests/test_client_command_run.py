import pytest

from dsd_pythonanywhere.client import CommandRun


@pytest.fixture
def sample_output():
    """Sample raw output from PythonAnywhere console."""
    return (
        "\r\nPreparing execution environment... OK\r\nReversing the polarity of the neutron flow... OK\r\n"
        "Loading Bash interpreter...\x1b[;H\x1b[2J\x1b[?2004h\x1b[0;0m19:34 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0m\r\x1b[K"
        "\x1b[0;0m19:34 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0mls\r\n\x1b[?2004l\r"
        "README.txt  dsd-testproj  foo  venv\r\n"
        "\x1b[?2004h\x1b[0;0m19:34 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0mls -lh\r\n\x1b[?2004l\r"
        "total 16K\r\n"
        "-rwxr-xr-x 1 copelco registered_users  232 Sep 11 15:29 README.txt\r\n"
        "drwxrwxr-x 6 copelco registered_users 4.0K Sep 22 15:50 dsd-testproj\r\n"
        "drwxrwxr-x 6 copelco registered_users 4.0K Sep 22 17:38 foo\r\n"
        "drwxrwxr-x 5 copelco registered_users 4.0K Sep 22 15:51 venv\r\n"
        "\x1b[?2004h\x1b[0;0m19:34 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0m\r\n\x1b[?2004l\r"
        "\x1b[?2004h\x1b[0;0m19:36 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0mecho hello\r\n\x1b[?2004l\r"
        "hello\r\n"
        "\x1b[?2004h\x1b[0;0m19:36 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0m"
    )


def test_finds_most_recent_prompt_line(sample_output: str):
    """find_most_recent_prompt_line finds the last prompt in output."""
    cmd_run = CommandRun(sample_output)
    prompt_line_index = cmd_run.find_most_recent_prompt_line()
    assert prompt_line_index is not None
    # Check that the line contains a prompt pattern
    assert "19:36 ~" in cmd_run.lines[prompt_line_index]
    assert "$" in cmd_run.lines[prompt_line_index]


def test_finds_prompt_line_with_expected_command(sample_output: str):
    """find_most_recent_prompt_line can filter by command."""
    cmd_run = CommandRun(sample_output)
    prompt_line_index = cmd_run.find_most_recent_prompt_line(expected_command="echo hello")
    assert prompt_line_index is not None
    assert "echo hello" in cmd_run.lines[prompt_line_index]


def test_returns_none_when_command_not_found(sample_output: str):
    """find_most_recent_prompt_line returns None when command not found."""
    cmd_run = CommandRun(sample_output)
    prompt_line_index = cmd_run.find_most_recent_prompt_line(expected_command="nonexistent")
    assert prompt_line_index is None


def test_extracts_command_output(sample_output: str):
    """extract_command_output returns output between command and next prompt."""
    cmd_run = CommandRun(sample_output)
    output = cmd_run.extract_command_output(expected_command="echo hello")
    assert output == "hello"


def test_extracts_multiline_command_output(sample_output: str):
    """extract_command_output handles multiline output."""
    cmd_run = CommandRun(sample_output)
    output = cmd_run.extract_command_output(expected_command="ls -lh")
    assert output is not None
    assert "total 16K" in output
    assert "README.txt" in output
    assert "dsd-testproj" in output


def test_returns_none_for_missing_command(sample_output):
    """extract_command_output returns None when command not found."""
    cmd_run = CommandRun(sample_output)
    output = cmd_run.extract_command_output(expected_command="nonexistent")
    assert output is None


def test_is_command_finished_returns_true_for_empty_prompt(sample_output: str):
    """is_command_finished returns True when prompt is empty."""
    cmd_run = CommandRun(sample_output)
    assert cmd_run.is_command_finished() is True


def test_is_command_finished_returns_false_during_execution():
    """is_command_finished returns False when command is still running."""
    # Output with command still executing (prompt has command text)
    running_output = "\x1b[0;0m19:34 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0mls\r\n"
    cmd_run = CommandRun(running_output)
    assert cmd_run.is_command_finished() is False


def test_is_command_finished_returns_false_when_no_prompt():
    """is_command_finished returns False when no prompt found."""
    cmd_run = CommandRun("some output with no prompt")
    assert cmd_run.is_command_finished() is False


def test_is_command_finished_handles_bracketed_paste_mode():
    """is_command_finished correctly strips bracketed paste mode escape sequences."""
    # Real output from PythonAnywhere with bracketed paste mode (\x1b[?2004h)
    output_with_bracketed_paste = (
        "Successfully installed Django-5.1.15\r\n"
        "Setup complete!!!\r\n"
        "\x1b[?2004h\x1b[0;0m16:08 ~\x1b[0;33m \x1b[1;32m$ \x1b[0;0m"
    )
    cmd_run = CommandRun(output_with_bracketed_paste)
    assert cmd_run.is_command_finished() is True
