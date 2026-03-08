"""E2E test fixtures."""

import pytest


@pytest.fixture(scope="session")
def base_url():
    return "https://backend-production-e740.up.railway.app"
