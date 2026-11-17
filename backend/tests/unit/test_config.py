"""Unit tests for configuration loading and security (Spec 8.6)."""

from __future__ import annotations

import ipaddress
from pathlib import Path
import pytest

from app.core.config import ConfigError, Settings
from app.core.dependencies import verify_api_key


def test_from_env_valid():
    env = {
        "NETSENTRY_API_KEY": "super-secret-key-at-least-16-chars",
        "NETSENTRY_DB_PATH": "/tmp/custom_netsentry.db",
        "NETSENTRY_AUTH_DISABLED": "0",
        "NETSENTRY_CORS_ORIGINS": "http://localhost:3000, https://app.example.com",
        "NETSENTRY_ALLOWED_NETWORKS": "10.0.0.0/16, 192.168.1.0/24",
        "NETSENTRY_ENABLE_DOCS": "1",
        "NETSENTRY_SSH_USERNAME": "admin",
        "NETSENTRY_SSH_PASSWORD": "SecretPassword123!",
        "NETSENTRY_ENABLE_SECRET": "EnableSecret456!",
    }

    settings = Settings.from_env(env)
    assert settings.api_key == "super-secret-key-at-least-16-chars"
    assert settings.db_path == Path("/tmp/custom_netsentry.db")
    assert settings.auth_disabled is False
    assert settings.cors_origins == ("http://localhost:3000", "https://app.example.com")
    assert settings.allowed_networks == (
        ipaddress.ip_network("10.0.0.0/16"),
        ipaddress.ip_network("192.168.1.0/24"),
    )
    assert settings.enable_docs is True
    assert settings.default_credentials is not None
    assert settings.default_credentials.username == "admin"
    assert settings.default_credentials.password == "SecretPassword123!"
    assert settings.default_credentials.enable_secret == "EnableSecret456!"


def test_from_env_defaults():
    env = {
        "NETSENTRY_API_KEY": "valid-secret-key-16-characters-long",
    }
    settings = Settings.from_env(env)
    assert settings.auth_disabled is False
    assert settings.cors_origins == ()
    assert settings.allowed_networks == ()
    assert settings.enable_docs is True
    assert settings.default_credentials is None
    assert settings.db_path.name == "netsentry.db"


def test_from_env_missing_api_key_raises_config_error():
    env = {}
    with pytest.raises(ConfigError, match="NETSENTRY_API_KEY.*required"):
        Settings.from_env(env)


def test_from_env_short_api_key_raises_config_error():
    env = {"NETSENTRY_API_KEY": "too-short"}
    with pytest.raises(ConfigError, match="at least 16 characters"):
        Settings.from_env(env)


def test_from_env_auth_disabled_allows_missing_or_short_key():
    for flag in ("1", "true", "yes", "True", "YES"):
        settings = Settings.from_env({"NETSENTRY_AUTH_DISABLED": flag})
        assert settings.auth_disabled is True
        assert settings.api_key is None

    settings_short = Settings.from_env({
        "NETSENTRY_AUTH_DISABLED": "1",
        "NETSENTRY_API_KEY": "short",
    })
    assert settings_short.auth_disabled is True
    assert settings_short.api_key == "short"


def test_from_env_invalid_cidr_raises_config_error():
    env = {
        "NETSENTRY_API_KEY": "valid-secret-key-16-characters-long",
        "NETSENTRY_ALLOWED_NETWORKS": "10.0.0.0/16, not-a-cidr/99",
    }
    with pytest.raises(ConfigError, match="Invalid CIDR network"):
        Settings.from_env(env)


def test_settings_repr_never_leaks_secrets():
    settings = Settings.from_env({
        "NETSENTRY_API_KEY": "SUPER_SECRET_API_KEY_12345",
        "NETSENTRY_SSH_USERNAME": "admin",
        "NETSENTRY_SSH_PASSWORD": "SUPER_SECRET_SSH_PASSWORD_12345",
        "NETSENTRY_ENABLE_SECRET": "SUPER_SECRET_ENABLE_SECRET_12345",
    })

    representation = repr(settings)
    assert "SUPER_SECRET_API_KEY_12345" not in representation
    assert "SUPER_SECRET_SSH_PASSWORD_12345" not in representation
    assert "SUPER_SECRET_ENABLE_SECRET_12345" not in representation


def test_verify_api_key():
    expected = "valid-secret-api-key-12345"

    assert verify_api_key("valid-secret-api-key-12345", expected) is True
    assert verify_api_key("wrong-key-with-same-length!", expected) is False
    assert verify_api_key(None, expected) is False
    assert verify_api_key("", expected) is False
    assert verify_api_key("valid-secret-api-key-12345", None) is False

    # auth_disabled=True always returns True
    assert verify_api_key(None, None, auth_disabled=True) is True
    assert verify_api_key("any", None, auth_disabled=True) is True
