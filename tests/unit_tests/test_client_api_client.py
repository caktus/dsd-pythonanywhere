import pytest
import requests

from dsd_pythonanywhere.client import APIClient


@pytest.fixture
def api_client(mocker):
    """APIClient instance with mocked environment."""
    mocker.patch.dict("os.environ", {"API_TOKEN": "test_token_12345"})
    return APIClient(username="testuser")


def test_api_client_init(mocker):
    """APIClient initializes with username and token from environment."""
    mocker.patch.dict("os.environ", {"API_TOKEN": "my_secret_token"})
    client = APIClient(username="myuser")

    assert client.username == "myuser"
    assert client.token == "my_secret_token"
    assert "Authorization" in client.session.headers
    assert client.session.headers["Authorization"] == "Token my_secret_token"


def test_hostname_default(api_client, mocker):
    """_hostname returns default PythonAnywhere domain."""
    mocker.patch.dict("os.environ", {}, clear=True)
    assert api_client._hostname == "www.pythonanywhere.com"


def test_hostname_custom_domain(mocker):
    """_hostname uses custom domain from environment."""
    mocker.patch.dict(
        "os.environ",
        {"API_TOKEN": "token", "PYTHONANYWHERE_DOMAIN": "pythonanywhere.eu"},
    )
    client = APIClient(username="testuser")
    assert client._hostname == "www.pythonanywhere.eu"


def test_base_url_construction(api_client):
    """_base_url constructs correct API endpoint URLs."""
    consoles_url = api_client._base_url("consoles")
    assert consoles_url == "https://www.pythonanywhere.com/api/v0/user/testuser/consoles"

    files_url = api_client._base_url("files")
    assert files_url == "https://www.pythonanywhere.com/api/v0/user/testuser/files"


def test_request_success(api_client, mocker):
    """request makes successful API call and returns response."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'
    mock_response.raise_for_status.return_value = None

    mocker.patch.object(api_client.session, "request", return_value=mock_response)

    response = api_client.request(method="GET", url="https://example.com/api/test")

    api_client.session.request.assert_called_once_with(
        method="GET", url="https://example.com/api/test/"
    )
    assert response == mock_response


def test_request_handles_errors(api_client, mocker):
    """request logs errors and raises when raise_for_status is True."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"
    mock_response.json.return_value = {"error": "Not found"}
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=mock_response
    )

    mocker.patch.object(api_client.session, "request", return_value=mock_response)

    with pytest.raises(requests.exceptions.HTTPError):
        api_client.request(method="GET", url="https://example.com/api/test")
