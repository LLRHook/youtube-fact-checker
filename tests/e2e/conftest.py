"""E2E test fixtures."""

import os
import pytest


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("E2E_BASE_URL", "http://localhost:8000")
