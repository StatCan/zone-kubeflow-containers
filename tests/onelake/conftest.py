import pytest


@pytest.fixture(scope="function", autouse=True)
def cleanup_containers():
    """OneLake unit tests do not create Docker containers."""
    yield
