"""Automatically run by pytest to set up test infrastructure."""

import re
from pathlib import Path
from typing import Dict

import pytest
import requests_mock

import openedx_webhooks
import openedx_webhooks.utils
import openedx_webhooks.info
from openedx_webhooks import settings

from .fake_github import FakeGitHub
from .fake_jira import FakeJira


@pytest.fixture
def requests_mocker():
    """Make requests_mock available as a fixture."""
    mocker = requests_mock.Mocker(real_http=False, case_sensitive=True)
    mocker.start()
    try:
        yield mocker
    finally:
        mocker.stop()

# URLs we use to grab data from GitHub.  We use requests_mock to provide
# canned data during tests.
DATA_REGEX = re.compile(r"https://raw.githubusercontent.com/([^/]+/[^/]+)/HEAD/(.*)")

@pytest.fixture
def fake_repo_data(requests_mocker):
    """A fixture to use local files instead of GitHub-fetched data files."""

    def _repo_data_callback(request, context):
        """Read repo_data data from local data."""
        m = re.fullmatch(DATA_REGEX, request.url)
        assert m, f"{request.url = }"
        repo_data_dir = Path(__file__).parent / "repo_data"
        file_path = repo_data_dir / "/".join(m.groups())
        if file_path.exists():
            return file_path.read_text()
        else:
            context.status_code = 404
            return "No such file"

    requests_mocker.get(DATA_REGEX, text=_repo_data_callback)


@pytest.fixture(scope="session", autouse=True)
def hard_cache_yaml_data_files(session_mocker) -> None:
    """
    Reading yaml files is slowish, and these data files don't change.
    Read them once per test run, and re-use the data.
    """
    real_read_yaml_data_file = openedx_webhooks.info._read_yaml_data_file
    data_files: Dict[str, Dict] = {}
    def new_read_yaml_data_file(filename):
        data = data_files.get(filename)
        if data is None:
            data = real_read_yaml_data_file(filename)
            data_files[filename] = data
        return data
    session_mocker.patch("openedx_webhooks.info._read_yaml_data_file", new_read_yaml_data_file)


def pytest_addoption(parser):
    parser.addoption(
        "--percent-404",
        action="store",
        help="What percent of HTTP requests should fail with a 404",
        default="0",
    )


@pytest.fixture(autouse=True)
def settings_for_tests(mocker):
    for name, value in vars(settings.TestSettings).items():
        if name.isupper():
            mocker.patch(f"openedx_webhooks.settings.{name}", value)


@pytest.fixture
def fake_github(pytestconfig, mocker, requests_mocker, fake_repo_data):
    fraction_404 = float(pytestconfig.getoption("percent_404")) / 100.0
    the_fake_github = FakeGitHub(login="webhook-bot", fraction_404=fraction_404)
    the_fake_github.install_mocks(requests_mocker)
    if fraction_404:
        # Make the retry sleep a no-op so it won't slow the tests.
        mocker.patch("openedx_webhooks.utils.retry_sleep", lambda x: None)
    return the_fake_github


@pytest.fixture
def fake_jira(requests_mocker):
    the_fake_jira = FakeJira(settings.JIRA_SERVER)
    the_fake_jira.install_mocks(requests_mocker)
    return the_fake_jira


@pytest.fixture(autouse=True)
def configure_flask_app():
    """
    Needed to make the app understand it's running under HTTPS, and have Flask
    initialized properly.
    """
    app = openedx_webhooks.create_app(config="testing")
    with app.test_request_context('/', base_url="https://openedx-webhooks.herokuapp.com"):
        yield


@pytest.fixture(autouse=True)
def reset_all_memoized_functions():
    """Clears the values cached by @memoize before each test. Applied automatically."""
    openedx_webhooks.utils.clear_memoized_values()


@pytest.fixture(params=[
    pytest.param(False, id="pr:closed"),
    pytest.param(True, id="pr:merged"),
])
def is_merged(request):
    """Makes tests try both merged and closed pull requests."""
    return request.param


@pytest.fixture(params=[
    pytest.param(False, id="jira:no"),
    pytest.param(True, id="jira:yes"),
])
def has_jira(request, mocker):
    """Makes tests try both with and without accessing Jira."""
    mocker.patch(
        "openedx_webhooks.settings.JIRA_SERVER",
        settings.TestSettings.JIRA_SERVER if request.param else None
    )
    return request.param
