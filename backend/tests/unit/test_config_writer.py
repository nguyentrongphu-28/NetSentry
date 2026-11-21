"""Unit tests for ConfigWriter, CiscoIOSConfigWriter, and FakeConfigWriter (Spec 10.2)."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from app.connectors.cisco_ios_connector import CiscoIOSConnector
from app.connectors.cisco_ios_writer import CiscoIOSConfigWriter
from app.connectors.fake_config_writer import FakeConfigWriter, FakeConfigWriterFactory
from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.errors import (
    CommandNotAllowedError,
    WriteAuthFailedError,
    WriteConnectionError,
    WriteRejectedError,
)
from app.factories.config_writer_factory import DefaultConfigWriterFactory


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.check_enable_mode.return_value = True
    session.send_config_set.return_value = "no ip http server\nOK"
    session.send_command.return_value = "Building configuration...\n[OK]"
    return session


class TestCiscoIOSConfigWriter:
    def test_apply_valid_remediation_commands_success(self, mock_session: MagicMock) -> None:
        session_factory = MagicMock(return_value=mock_session)
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        with writer:
            result = writer.apply(["no ip http server"])

        assert result.success is True
        assert len(result.commands) == 1
        assert result.commands[0].command == "no ip http server"
        assert result.commands[0].accepted is True

        # Assert config_mode was entered, command was sent as single line, exit_config_mode called
        mock_session.config_mode.assert_called_once()
        mock_session.send_config_set.assert_called_once_with(
            ["no ip http server"],
            enter_config_mode=False,
            exit_config_mode=False,
            read_timeout=60,
        )
        mock_session.exit_config_mode.assert_called_once()

    def test_apply_valid_rollback_commands_success(self, mock_session: MagicMock) -> None:
        session_factory = MagicMock(return_value=mock_session)
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        with writer:
            result = writer.apply(["ip http server"], is_rollback=True)

        assert result.success is True
        assert len(result.commands) == 1
        assert result.commands[0].command == "ip http server"
        assert result.commands[0].accepted is True

    def test_command_outside_allowlist_rejected_before_device_touch(
        self, mock_session: MagicMock
    ) -> None:
        session_factory = MagicMock(return_value=mock_session)
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        forbidden_commands = [
            "reload",
            "conf t",
            "no ip http server\nreload",
            "service password-encryption; write erase",
            "ip http server",  # rollback command not allowed on remediation path
        ]

        with writer:
            for forbidden in forbidden_commands:
                with pytest.raises(CommandNotAllowedError):
                    writer.apply([forbidden], is_rollback=False)

        # Device config_mode should NEVER have been entered for forbidden commands
        mock_session.config_mode.assert_not_called()

    def test_device_error_indicator_triggers_write_rejected_error(
        self, mock_session: MagicMock
    ) -> None:
        mock_session.send_config_set.return_value = "% Invalid input detected at '^' marker."
        session_factory = MagicMock(return_value=mock_session)
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        with writer:
            with pytest.raises(WriteRejectedError, match="% Invalid input"):
                writer.apply(["no ip http server"])

        # exit_config_mode must be called even on rejection
        mock_session.exit_config_mode.assert_called_once()

    def test_auth_failure_maps_to_write_auth_failed_error(self) -> None:
        session_factory = MagicMock(side_effect=NetmikoAuthenticationException("Auth failed"))
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        with pytest.raises(WriteAuthFailedError):
            with writer:
                pass

    def test_timeout_maps_to_write_connection_error(self) -> None:
        session_factory = MagicMock(side_effect=NetmikoTimeoutException("Timeout"))
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        with pytest.raises(WriteConnectionError):
            with writer:
                pass

    def test_save_config_strictly_sends_write_memory(self, mock_session: MagicMock) -> None:
        session_factory = MagicMock(return_value=mock_session)
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        with writer:
            writer.save_config()

        mock_session.send_command.assert_called_once_with("write memory", read_timeout=60)

    def test_save_config_error_handling(self, mock_session: MagicMock) -> None:
        mock_session.send_command.return_value = "% Configuration save failed"
        session_factory = MagicMock(return_value=mock_session)
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password="secret_write_password",
            session_factory=session_factory,
        )

        with writer:
            with pytest.raises(WriteRejectedError, match="Save config failed"):
                writer.save_config()

    def test_no_credentials_in_exceptions(self, mock_session: MagicMock) -> None:
        sentinel_pass = "SENTINEL_SECRET_WRITE_PASS_12345"
        session_factory = MagicMock(side_effect=NetmikoAuthenticationException(f"Failed {sentinel_pass}"))
        writer = CiscoIOSConfigWriter(
            host="192.168.1.1",
            port=22,
            username="admin_write",
            password=sentinel_pass,
            session_factory=session_factory,
        )

        with pytest.raises(WriteAuthFailedError) as exc_info:
            with writer:
                pass

        assert sentinel_pass not in str(exc_info.value)

    def test_read_connector_still_strictly_rejects_configuration_commands(self) -> None:
        target = DeviceTarget(device_id="Router-01", host="192.168.1.1", port=22, platform="cisco_ios")
        creds = Credentials(username="read_user", password="read_password")
        read_conn = CiscoIOSConnector(target, creds)

        # Config commands MUST be forbidden in read connector
        for cmd in ("conf t", "configure terminal", "no ip http server", "write memory"):
            with pytest.raises(CommandNotAllowedError):
                read_conn._normalize_command(cmd)


class TestFakeConfigWriterAndFactory:
    def test_fake_config_writer_records_and_applies(self) -> None:
        writer = FakeConfigWriter()
        with writer:
            res = writer.apply(["no ip http server"])
            assert res.success is True
            writer.save_config()

        assert writer.applied_commands == ["no ip http server"]
        assert writer.save_config_called is True

    def test_fake_config_writer_raises_when_configured(self) -> None:
        writer = FakeConfigWriter(raise_if_called=True)
        with pytest.raises(RuntimeError, match="raise_if_called=True"):
            with writer:
                pass

    def test_default_factory_creates_writer_or_validates(self) -> None:
        factory = DefaultConfigWriterFactory("user_w", "pass_w", timeout=30)
        writer = factory.create_writer("r1", "192.168.1.1", 22, "cisco_ios")
        assert isinstance(writer, CiscoIOSConfigWriter)

        unsupported_factory = DefaultConfigWriterFactory("user_w", "pass_w")
        with pytest.raises(ValueError, match="Unsupported platform"):
            unsupported_factory.create_writer("r1", "192.168.1.1", 22, "juniper_junos")

        empty_factory = DefaultConfigWriterFactory("", "")
        with pytest.raises(WriteAuthFailedError):
            empty_factory.create_writer("r1", "192.168.1.1", 22, "cisco_ios")
