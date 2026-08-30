import pytest


def pytest_addoption(parser):
    parser.addoption("--locale", action="store", default=None)
    parser.addoption("--screenshot-output", action="store", default=None)


@pytest.fixture(scope="session")
def target_locale(request):
    return request.config.option.locale


@pytest.fixture(scope="session")
def screenshot_output(request):
    return request.config.option.screenshot_output
