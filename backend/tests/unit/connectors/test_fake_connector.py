"""Unit tests for FakeConnector."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.connectors.fake_connector import FakeConnector
from app.domain.errors import AuthenticationFailedError, ConnectionTimeoutError


def test_fake_connector_basic_properties():
    connector = FakeConnector(config_text="hostname ROUTER1\n", hostname="ROUTER1")
    assert connector.platform == "cisco_ios"
    assert connector.get_hostname() == "ROUTER1"
    assert connector.get_running_config() == "hostname ROUTER1\n"
    assert connector.connect_calls == 0
    assert connector.close_calls == 0


def test_fake_connector_connect_and_close():
    connector = FakeConnector(config_text="hostname R1")
    connector.connect()
    assert connector.connect_calls == 1
    assert connector.is_connected is True

    connector.close()
    assert connector.close_calls == 1
    assert connector.is_connected is False


def test_fake_connector_context_manager():
    connector = FakeConnector(config_text="hostname R1")
    with connector as conn:
        assert conn is connector
        assert connector.connect_calls == 1
        assert connector.close_calls == 0
        assert connector.is_connected is True

    assert connector.close_calls == 1
    assert connector.is_connected is False


def test_fake_connector_fail_on():
    connector = FakeConnector(config_text="hostname R1", fail_on=AuthenticationFailedError)
    with pytest.raises(AuthenticationFailedError):
        connector.connect()
    assert connector.connect_calls == 1

    connector_timeout = FakeConnector(config_text="hostname R1", fail_on=ConnectionTimeoutError)
    with pytest.raises(ConnectionTimeoutError):
        connector_timeout.connect()


def test_fake_connector_from_file(tmp_path: Path):
    cfg_file = tmp_path / "test.cfg"
    cfg_file.write_text("hostname TEST-BOX\nline vty 0 4\n", encoding="utf-8")

    connector = FakeConnector.from_file(cfg_file, hostname="TEST-BOX")
    assert connector.get_hostname() == "TEST-BOX"
    assert connector.get_running_config() == "hostname TEST-BOX\nline vty 0 4\n"
