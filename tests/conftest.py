"""Production circuit state must persist across calls, but not across test cases."""
import pytest

from core.assistant_operations import provider_health


@pytest.fixture(autouse=True)
def isolated_provider_circuits():
    provider_health.reset()
    yield
    provider_health.reset()
