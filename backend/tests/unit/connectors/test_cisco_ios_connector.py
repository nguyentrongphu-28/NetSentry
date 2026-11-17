"""Unit tests for CiscoIOSConnector with Netmiko simulation."""

from __future__ import annotations

import logging
from pathlib import Path
import socket
from typing import Any
import pytest

from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoBaseException,
    NetmikoTimeoutException,
    ReadTimeout,
)
import paramiko

from app.connectors.cisco_ios_connector import CiscoIOSConnector
from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.errors import (
    AuthenticationFailedError,
    CommandNotAllowedError,
    ConfigCollectionError,
    ConnectionFailedError,
    ConnectionTimeoutError,
)


class FakeSession:
    """Simulates a Netmiko connection session."""

    def __init__(
        self,
        prompt: str = "Router#",
        command_responses: dict[str, str] | None = None,
        raise_on_send: Exception | None = None,
        raise_on_disconnect: Exception | None = None,
        raise_on_find_prompt: Exception | None = None,
        raise_on_enable: Exception | None = None,
    ) -> None:
        self.prompt = prompt
        self.command_responses = command_responses or {
            "show running-config": "hostname Router\ninterface GigabitEthernet0/0\n",
            "show version": "Cisco IOS Software, Version 15.6\n",
        }
        self.raise_on_send = raise_on_send
        self.raise_on_disconnect = raise_on_disconnect
        self.raise_on_find_prompt = raise_on_find_prompt
        self.raise_on_enable = raise_on_enable
        self.commands_received: list[str] = []
        self.enable_called: bool = False
        self.disconnected: bool = False

    def find_prompt(self) -> str:
        if self.raise_on_find_prompt is not None:
            raise self.raise_on_find_prompt
        return self.prompt

    def send_command(self, command: str, read_timeout: int = 60) -> str:
        self.commands_received.append(command)
        if self.raise_on_send is not None:
            raise self.raise_on_send
        return self.command_responses.get(command, "")

    def enable(self) -> None:
        self.enable_called = True
        if self.raise_on_enable is not None:
            raise self.raise_on_enable
        self.prompt = self.prompt.rstrip(">") + "#"

    def check_enable_mode(self) -> bool:
        return self.prompt.endswith("#")

    def disconnect(self) -> None:
        self.disconnected = True
        if self.raise_on_disconnect is not None:
            raise self.raise_on_disconnect


@pytest.fixture
def target() -> DeviceTarget:
    return DeviceTarget(device_id="R1", host="10.0.0.1", platform="cisco_ios", port=22)


@pytest.fixture
def credentials() -> Credentials:
    return Credentials(username="fake-user", password="FAKE-SSH-PW", enable_secret="FAKE-ENABLE-PW")


class TestCiscoIOSConnectorBasics:
    def test_success_get_running_config_and_hostname(self, target: DeviceTarget, credentials: Credentials):
        fake_session = FakeSession(prompt="Router#")
        connector = CiscoIOSConnector(
            target,
            credentials,
            session_factory=lambda **kw: fake_session,
        )

        with connector:
            cfg = connector.get_running_config()
            hostname = connector.get_hostname()

        assert "hostname Router" in cfg
        assert hostname == "Router"
        assert fake_session.commands_received == ["show running-config"]
        assert fake_session.disconnected is True

    def test_session_factory_arguments(self, target: DeviceTarget, credentials: Credentials, tmp_path: Path):
        passed_params: dict[str, Any] = {}

        def factory(**kw: Any) -> FakeSession:
            passed_params.update(kw)
            return FakeSession()

        # Without ssh_config_file
        connector = CiscoIOSConnector(target, credentials, session_factory=factory)
        connector.connect()
        assert passed_params["device_type"] == "cisco_ios"
        assert passed_params["host"] == "10.0.0.1"
        assert passed_params["port"] == 22
        assert passed_params["username"] == "fake-user"
        assert passed_params["password"] == "FAKE-SSH-PW"
        assert passed_params["secret"] == "FAKE-ENABLE-PW"
        assert passed_params["use_keys"] is False
        assert passed_params["allow_agent"] is False
        assert "ssh_config_file" not in passed_params
        connector.close()

        # With nonexistent ssh_config_file
        passed_params.clear()
        connector2 = CiscoIOSConnector(
            target,
            credentials,
            ssh_config_file=str(tmp_path / "nonexistent.conf"),
            session_factory=factory,
        )
        connector2.connect()
        assert "ssh_config_file" not in passed_params
        connector2.close()

        # With existing ssh_config_file
        real_cfg = tmp_path / "ssh_config"
        real_cfg.write_text("Host *\n  ServerAliveInterval 60\n")
        passed_params.clear()
        connector3 = CiscoIOSConnector(
            target,
            credentials,
            ssh_config_file=str(real_cfg),
            session_factory=factory,
        )
        connector3.connect()
        assert passed_params.get("ssh_config_file") == str(real_cfg)
        connector3.close()

    def test_connect_when_already_connected_is_noop(self, target: DeviceTarget, credentials: Credentials):
        call_count = 0

        def factory(**kw: Any) -> FakeSession:
            nonlocal call_count
            call_count += 1
            return FakeSession()

        connector = CiscoIOSConnector(target, credentials, session_factory=factory)
        connector.connect()
        connector.connect()
        assert call_count == 1
        connector.close()


class TestCiscoIOSConnectorAllowlist:
    @pytest.mark.parametrize(
        "bad_command",
        [
            "configure terminal",
            "conf t",
            "show running-config; reload",
            "show run",
            "show running-config | include password",
            "write memory",
            "write",
            "reload",
            "copy running-config startup-config",
            "delete flash:test",
            "show running-config\nreload",
            "show running-config\r",
            "show running-config; echo hello",
            "show running-config |",
            "show version | include Cisco",
        ],
    )
    def test_disallowed_commands_rejected_before_session(
        self,
        target: DeviceTarget,
        credentials: Credentials,
        bad_command: str,
    ):
        fake_session = FakeSession()
        connector = CiscoIOSConnector(
            target,
            credentials,
            session_factory=lambda **kw: fake_session,
        )
        connector.connect()

        with pytest.raises(CommandNotAllowedError) as exc_info:
            connector._run(bad_command)

        assert exc_info.value.code == "COMMAND_NOT_ALLOWED"
        assert len(fake_session.commands_received) == 0


class TestCiscoIOSConnectorPrivilegedMode:
    def test_unprivileged_prompt_with_enable_secret(self, target: DeviceTarget, credentials: Credentials):
        fake_session = FakeSession(prompt="Router>")
        connector = CiscoIOSConnector(
            target,
            credentials,
            session_factory=lambda **kw: fake_session,
        )
        connector.connect()

        assert fake_session.enable_called is True
        assert fake_session.prompt == "Router#"
        connector.close()

    def test_unprivileged_prompt_without_enable_secret_raises_and_closes(self, target: DeviceTarget):
        creds_no_secret = Credentials(username="fake-user", password="FAKE-SSH-PW", enable_secret=None)
        fake_session = FakeSession(prompt="Router>")
        connector = CiscoIOSConnector(
            target,
            creds_no_secret,
            session_factory=lambda **kw: fake_session,
        )

        with pytest.raises(ConfigCollectionError, match="Privileged EXEC mode required") as exc_info:
            connector.connect()

        assert exc_info.value.code == "COLLECTION_FAILED"
        assert fake_session.disconnected is True
        assert connector._session is None

    def test_unprivileged_prompt_enable_fails_maps_to_auth_failed_and_closes(
        self,
        target: DeviceTarget,
        credentials: Credentials,
    ):
        fake_session = FakeSession(prompt="Router>", raise_on_enable=ValueError("Failed to enter enable mode"))
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)

        with pytest.raises(AuthenticationFailedError) as exc_info:
            connector.connect()

        assert exc_info.value.code == "AUTH_FAILED"
        assert "Enable mode authentication failed" in str(exc_info.value)
        assert fake_session.disconnected is True
        assert connector._session is None



class TestCiscoIOSConnectorErrorMapping:
    def test_auth_failed_mapping(self, target: DeviceTarget, credentials: Credentials):
        def factory(**kw: Any) -> Any:
            raise NetmikoAuthenticationException("Netmiko auth failure")

        connector = CiscoIOSConnector(target, credentials, session_factory=factory)
        with pytest.raises(AuthenticationFailedError) as exc_info:
            connector.connect()
        assert exc_info.value.code == "AUTH_FAILED"
        assert "Netmiko auth failure" not in str(exc_info.value)
        assert target.host in str(exc_info.value)

    def test_timeout_failed_mapping(self, target: DeviceTarget, credentials: Credentials):
        def factory(**kw: Any) -> Any:
            raise NetmikoTimeoutException("Netmiko timeout failure")

        connector = CiscoIOSConnector(target, credentials, session_factory=factory)
        with pytest.raises(ConnectionTimeoutError) as exc_info:
            connector.connect()
        assert exc_info.value.code == "CONNECT_TIMEOUT"

    def test_ssh_connection_failed_mapping(self, target: DeviceTarget, credentials: Credentials):
        for exc in (paramiko.SSHException("SSH low level fail"), OSError("Socket error"), EOFError("EOF")):
            def factory(**kw: Any) -> Any:
                raise exc

            connector = CiscoIOSConnector(target, credentials, session_factory=factory)
            with pytest.raises(ConnectionFailedError) as exc_info:
                connector.connect()
            assert exc_info.value.code == "CONNECT_FAILED"

    def test_paramiko_auth_exception_mapping(self, target: DeviceTarget, credentials: Credentials):
        def factory(**kw: Any) -> Any:
            raise paramiko.AuthenticationException("Paramiko auth failed")

        connector = CiscoIOSConnector(target, credentials, session_factory=factory)
        with pytest.raises(AuthenticationFailedError) as exc_info:
            connector.connect()
        assert exc_info.value.code == "AUTH_FAILED"

    def test_timeout_error_and_socket_timeout_mapping(self, target: DeviceTarget, credentials: Credentials):
        for exc in (TimeoutError("Generic timeout"), socket.timeout("Socket timed out")):
            def factory(**kw: Any) -> Any:
                raise exc

            connector = CiscoIOSConnector(target, credentials, session_factory=factory)
            with pytest.raises(ConnectionTimeoutError) as exc_info:
                connector.connect()
            assert exc_info.value.code == "CONNECT_TIMEOUT"

    def test_error_after_session_creation_closes_session(self, target: DeviceTarget, credentials: Credentials):
        fake_session = FakeSession(raise_on_find_prompt=NetmikoBaseException("find_prompt failed"))
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)

        with pytest.raises(ConfigCollectionError):
            connector.connect()

        assert fake_session.disconnected is True
        assert connector._session is None

    def test_marker_in_later_line_does_not_fail(self, target: DeviceTarget, credentials: Credentials):
        valid_cfg_with_marker = (
            "!\n"
            "interface GigabitEthernet0/0\n"
            " description Link with % Invalid input detected in banner\n"
            " ip address 10.0.0.1 255.255.255.0\n"
            "!\n"
        )
        fake_session = FakeSession(
            command_responses={"show running-config": valid_cfg_with_marker}
        )
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)
        connector.connect()
        output = connector.get_running_config()
        assert output == valid_cfg_with_marker


    def test_read_timeout_maps_to_connection_timeout_error(self, target: DeviceTarget, credentials: Credentials):
        fake_session = FakeSession(raise_on_send=ReadTimeout("Pattern not detected"))
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)
        connector.connect()

        with pytest.raises(ConnectionTimeoutError) as exc_info:
            connector.get_running_config()
        assert exc_info.value.code == "CONNECT_TIMEOUT"

    def test_generic_netmiko_exception_maps_to_collection_error(self, target: DeviceTarget, credentials: Credentials):
        fake_session = FakeSession(raise_on_send=NetmikoBaseException("General Netmiko error"))
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)
        connector.connect()

        with pytest.raises(ConfigCollectionError) as exc_info:
            connector.get_running_config()
        assert exc_info.value.code == "COLLECTION_FAILED"

    @pytest.mark.parametrize(
        "error_output",
        [
            "% Invalid input detected at '^' marker.",
            "% Authorization failed.",
            "% Ambiguous command: 'show'",
            "% Incomplete command.",
            "",
            "   \n\t  ",
        ],
    )
    def test_error_or_empty_output_raises_collection_error(
        self,
        target: DeviceTarget,
        credentials: Credentials,
        error_output: str,
    ):
        fake_session = FakeSession(
            command_responses={"show running-config": error_output}
        )
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)
        connector.connect()

        with pytest.raises(ConfigCollectionError) as exc_info:
            connector.get_running_config()
        assert exc_info.value.code == "COLLECTION_FAILED"

    def test_commands_when_not_connected_raise_connection_failed(self, target: DeviceTarget, credentials: Credentials):
        connector = CiscoIOSConnector(target, credentials)
        with pytest.raises(ConnectionFailedError, match="Not connected"):
            connector.get_running_config()

        with pytest.raises(ConnectionFailedError, match="Not connected"):
            connector.get_hostname()


class TestCiscoIOSConnectorCloseAndLifecycle:
    def test_close_is_idempotent_and_handles_exceptions(self, target: DeviceTarget, credentials: Credentials):
        fake_session = FakeSession(raise_on_disconnect=RuntimeError("Disconnect socket closed unexpectedly"))
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)
        connector.connect()

        # Should not raise even if session.disconnect() raises
        connector.close()
        assert connector._session is None

        # Subsequent close is no-op and does not raise
        connector.close()
        assert connector._session is None

    def test_context_manager_always_closes(self, target: DeviceTarget, credentials: Credentials):
        fake_session = FakeSession()
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)

        try:
            with connector:
                raise RuntimeError("Unexpected failure during work")
        except RuntimeError:
            pass

        assert fake_session.disconnected is True
        assert connector._session is None


class TestCiscoIOSConnectorLeakPrevention:
    def test_no_credential_leak_in_logs_repr_or_str(
        self,
        target: DeviceTarget,
        credentials: Credentials,
        caplog: pytest.LogCaptureFixture,
    ):
        caplog.set_level(logging.DEBUG)

        fake_session = FakeSession(prompt="Router#")
        connector = CiscoIOSConnector(target, credentials, session_factory=lambda **kw: fake_session)

        with connector:
            cfg = connector.get_running_config()
            assert "hostname" in cfg

        # Check representation
        repr_str = repr(connector)
        assert "FAKE-SSH-PW" not in repr_str
        assert "FAKE-ENABLE-PW" not in repr_str
        assert "fake-user" not in repr_str
        assert "R1" in repr_str
        assert "10.0.0.1" in repr_str

        # Check log output
        log_text = caplog.text
        assert "FAKE-SSH-PW" not in log_text
        assert "FAKE-ENABLE-PW" not in log_text
        assert "fake-user" not in log_text
        # Command output should not be in logs
        assert "interface GigabitEthernet0/0" not in log_text

    def test_no_credential_leak_on_exception(
        self,
        target: DeviceTarget,
        credentials: Credentials,
        caplog: pytest.LogCaptureFixture,
    ):
        caplog.set_level(logging.DEBUG)

        def failing_factory(**kw: Any) -> Any:
            raise NetmikoAuthenticationException("Authentication failed for user fake-user with pw FAKE-SSH-PW")

        connector = CiscoIOSConnector(target, credentials, session_factory=failing_factory)
        with pytest.raises(AuthenticationFailedError) as exc_info:
            connector.connect()

        exc_str = str(exc_info.value)
        assert "FAKE-SSH-PW" not in exc_str
        assert "FAKE-ENABLE-PW" not in exc_str
        assert "fake-user" not in exc_str

        log_text = caplog.text
        assert "FAKE-SSH-PW" not in log_text
        assert "FAKE-ENABLE-PW" not in log_text
        assert "fake-user" not in log_text
