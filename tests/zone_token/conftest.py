import pytest


@pytest.fixture(scope="function", autouse=True)
def cleanup_containers():
    """Zone token unit tests do not create Docker containers."""
    yield
