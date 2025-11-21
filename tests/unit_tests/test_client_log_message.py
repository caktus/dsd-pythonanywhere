import logging

from dsd_pythonanywhere.client import log_message


def test_logs_to_logger(mocker):
    """log_message calls the logger with correct arguments."""
    mock_logger = mocker.patch("dsd_pythonanywhere.client.logger")
    log_message("Test message", level=logging.INFO)
    mock_logger.log.assert_called_once_with(logging.INFO, "Test message")


def test_writes_to_plugin_utils_when_stdout_exists(mocker):
    """log_message writes to plugin_utils when stdout is available."""
    mock_plugin_utils = mocker.patch("dsd_pythonanywhere.client.plugin_utils")
    mock_plugin_utils.dsd_config.stdout = mocker.MagicMock()
    log_message("Test output")
    mock_plugin_utils.write_output.assert_called_once_with("Test output")
