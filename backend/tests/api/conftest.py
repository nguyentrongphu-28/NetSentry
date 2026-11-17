"""Pytest fixtures for API testing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
import pytest
from starlette.testclient import TestClient

from app.connectors.fake_connector import FakeConnector
from app.core.config import Settings
from app.domain.entities.device import Credentials
from app.factories.connector_factory import ConnectorFactory
from app.main import create_app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "configs"
TEST_API_KEY = "test-api-key-with-16-plus-characters"


@pytest.fixture
def insecure_config_text() -> str:
    return (FIXTURES_DIR / "ios_insecure.cfg").read_text(encoding="utf-8")


@pytest.fixture
def secure_config_text() -> str:
    return (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    return tmp_path / "api_test.db"


@pytest.fixture
def connector_holder() -> dict[str, FakeConnector]:
    return {}


@pytest.fixture
def fake_connector_factory(
    insecure_config_text: str, connector_holder: dict[str, FakeConnector]
) -> ConnectorFactory:
    factory = ConnectorFactory()

    def create_fake(target, creds):
        if target.device_id in connector_holder:
            return connector_holder[target.device_id]
        conn = FakeConnector(config_text=insecure_config_text, hostname=f"Host-{target.device_id}")
        connector_holder[target.device_id] = conn
        return conn

    factory.register("cisco_ios", create_fake)
    return factory


@pytest.fixture
def default_settings(test_db_path: Path) -> Settings:
    return Settings(
        db_path=test_db_path,
        api_key=TEST_API_KEY,
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=True,
        default_credentials=Credentials(
            username="default_env_user",
            password="default_env_password123",
            enable_secret="default_env_enable_secret",
        ),
    )


@pytest.fixture
def app(default_settings: Settings, fake_connector_factory: ConnectorFactory):
    return create_app(default_settings, connector_factory=fake_connector_factory)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_client(app) -> TestClient:
    return TestClient(app, headers={"X-API-Key": TEST_API_KEY})
