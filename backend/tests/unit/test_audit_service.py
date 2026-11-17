"""Unit tests for AuditService."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any
import pytest

from app.connectors.fake_connector import FakeConnector
from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.errors import (
    AuthenticationFailedError,
    CommandNotAllowedError,
    ConfigCollectionError,
    ConnectionFailedError,
    ConnectionTimeoutError,
    NetSentryError,
    UnsupportedPlatformError,
)
from app.factories.connector_factory import ConnectorFactory
from app.rules.registry import build_default_engine
from app.services.audit_service import AuditService

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "configs"


class TrackableFakeConnector(FakeConnector):
    """FakeConnector subclass to inspect instance state after audit."""

    def __init__(self, *args: Any, raise_unexpected: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.raise_unexpected = raise_unexpected

    def connect(self) -> None:
        super().connect()
        if self.raise_unexpected:
            raise RuntimeError("secret-stuff internal failure")


@pytest.fixture
def target() -> DeviceTarget:
    return DeviceTarget(device_id="R1", host="10.0.0.1", platform="cisco_ios")


@pytest.fixture
def credentials() -> Credentials:
    return Credentials(username="admin", password="FAKE_PASSWORD_SECRET", enable_secret="FAKE_ENABLE_SECRET")


@pytest.fixture
def fake_clock():
    times = [
        datetime(2026, 11, 17, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 17, 10, 0, 5, tzinfo=timezone.utc),
    ]
    idx = 0

    def _clock() -> datetime:
        nonlocal idx
        val = times[min(idx, len(times) - 1)]
        idx += 1
        return val

    return _clock


def test_audit_device_insecure_config(target: DeviceTarget, credentials: Credentials, fake_clock):
    cfg_text = (FIXTURES_DIR / "ios_insecure.cfg").read_text(encoding="utf-8")
    fake_conn = TrackableFakeConnector(config_text=cfg_text, hostname="R1-INSECURE")

    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials)

    assert result.status == AuditStatus.COMPLETED
    assert result.device_id == "R1"
    assert result.platform == "cisco_ios"
    assert result.hostname == "R1-INSECURE"
    assert result.started_at == datetime(2026, 11, 17, 10, 0, 0, tzinfo=timezone.utc)
    assert result.finished_at == datetime(2026, 11, 17, 10, 0, 5, tzinfo=timezone.utc)
    assert result.fail_count == 8
    assert result.pass_count == 0
    assert fake_conn.close_calls == 1


def test_audit_device_secure_config(target: DeviceTarget, credentials: Credentials, fake_clock):
    cfg_text = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    fake_conn = TrackableFakeConnector(config_text=cfg_text, hostname="R1-SECURE")

    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials)

    assert result.status == AuditStatus.COMPLETED
    assert result.fail_count == 0
    assert result.pass_count == 8
    assert fake_conn.close_calls == 1


@pytest.mark.parametrize(
    ("error_cls", "expected_code"),
    [
        (AuthenticationFailedError, "AUTH_FAILED"),
        (ConnectionTimeoutError, "CONNECT_TIMEOUT"),
        (ConnectionFailedError, "CONNECT_FAILED"),
        (ConfigCollectionError, "COLLECTION_FAILED"),
        (CommandNotAllowedError, "COMMAND_NOT_ALLOWED"),
    ],
)
def test_audit_device_netsentry_errors(
    target: DeviceTarget,
    credentials: Credentials,
    fake_clock,
    error_cls: type[NetSentryError],
    expected_code: str,
):
    fake_conn = TrackableFakeConnector(config_text="hostname R1\n", fail_on=error_cls)
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials)

    assert result.status == AuditStatus.FAILED
    assert result.error_code == expected_code
    assert result.findings == ()
    assert fake_conn.close_calls == 1


def test_audit_device_unsupported_platform(credentials: Credentials, fake_clock):
    unknown_target = DeviceTarget(device_id="R1", host="10.0.0.1", platform="unknown_os")
    factory = ConnectorFactory()
    # No builder registered for unknown_os

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(unknown_target, credentials)

    assert result.status == AuditStatus.FAILED
    assert result.error_code == "UNSUPPORTED_PLATFORM"
    assert result.findings == ()


def test_audit_device_unexpected_exception_masks_secrets(target: DeviceTarget, credentials: Credentials, fake_clock):
    fake_conn = TrackableFakeConnector(config_text="hostname R1\n", raise_unexpected=True)
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials)

    assert result.status == AuditStatus.FAILED
    assert result.error_code == "INTERNAL_ERROR"
    assert "secret-stuff" not in str(result.error_message)
    assert result.error_message == "Unexpected error during audit"
    assert fake_conn.close_calls == 1


def test_audit_device_no_leak_in_json_output(target: DeviceTarget, credentials: Credentials, fake_clock):
    cfg_text = (FIXTURES_DIR / "ios_insecure.cfg").read_text(encoding="utf-8")
    fake_conn = TrackableFakeConnector(config_text=cfg_text, hostname="R1")
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials)

    json_str = json.dumps(result.to_dict())
    assert "FAKE_PASSWORD_SECRET" not in json_str
    assert "FAKE_ENABLE_SECRET" not in json_str
    assert not hasattr(result, "config_text")


def test_audit_device_hook_on_config_collected_success(target: DeviceTarget, credentials: Credentials, fake_clock):
    cfg_text = "hostname HOOK-ROUTER\nline vty 0 4\n"
    fake_conn = TrackableFakeConnector(config_text=cfg_text, hostname="HOOK-ROUTER")
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    collected: list[str] = []

    def hook(cfg: str) -> None:
        collected.append(cfg)

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials, on_config_collected=hook)

    assert result.status == AuditStatus.COMPLETED
    assert collected == [cfg_text]
    assert not hasattr(result, "config_text")


def test_audit_device_hook_error_does_not_fail_audit(
    target: DeviceTarget,
    credentials: Credentials,
    fake_clock,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.WARNING)
    cfg_text = "hostname HOOK-ROUTER\n"
    fake_conn = TrackableFakeConnector(config_text=cfg_text)
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    def failing_hook(cfg: str) -> None:
        raise OSError("Disk full / permission denied")

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials, on_config_collected=failing_hook)

    # Audit completes successfully despite hook failure
    assert result.status == AuditStatus.COMPLETED
    assert "on_config_collected hook failed" in caplog.text
    assert "OSError" in caplog.text
    # Config content should not be logged
    assert "hostname HOOK-ROUTER" not in caplog.text


def test_audit_device_connector_failure_does_not_call_hook(target: DeviceTarget, credentials: Credentials, fake_clock):
    fake_conn = TrackableFakeConnector(config_text="hostname R1\n", fail_on=ConnectionTimeoutError)
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    hook_called = False

    def hook(cfg: str) -> None:
        nonlocal hook_called
        hook_called = True

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials, on_config_collected=hook)

    assert result.status == AuditStatus.FAILED
    assert hook_called is False


def test_audit_device_netsentry_error_does_not_log_traceback(
    target: DeviceTarget,
    credentials: Credentials,
    fake_clock,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.DEBUG)
    fake_conn = TrackableFakeConnector(config_text="hostname R1\n", fail_on=AuthenticationFailedError)
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)

    service = AuditService(connector_factory=factory, engine=build_default_engine(), clock=fake_clock)
    result = service.audit_device(target, credentials)

    assert result.status == AuditStatus.FAILED
    assert "AUTH_FAILED" in caplog.text
    assert "Traceback" not in caplog.text
