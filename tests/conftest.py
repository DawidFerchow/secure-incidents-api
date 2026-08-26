from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(
            log_level="CRITICAL",
            seed_records=2_000,
            allowed_hosts=("testserver",),
        )
    )
    with TestClient(app) as test_client:
        yield test_client
