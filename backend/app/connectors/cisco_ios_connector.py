"""Cisco IOS SSH Device Connector implementation using Netmiko."""

from __future__ import annotations

import logging
import os
import socket
from typing import Any, Callable

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoBaseException,
    NetmikoTimeoutException,
    ReadTimeout,
)
import paramiko

from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.errors import (
    AuthenticationFailedError,
    CommandNotAllowedError,
    ConfigCollectionError,
    ConnectionFailedError,
    ConnectionTimeoutError,
    NetSentryError,
)
from app.domain.interfaces.device_connector import DeviceConnector

logger = logging.getLogger(__name__)


class CiscoIOSConnector(DeviceConnector):
    """SSH connector for Cisco IOS devices adhering to read-only security constraints."""

    platform: str = "cisco_ios"
    ALLOWED_COMMANDS: frozenset[str] = frozenset({"show running-config", "show version"})

    def __init__(
        self,
        target: DeviceTarget,
        credentials: Credentials,
        *,
        timeout: int = 15,
        command_timeout: int = 60,
        ssh_config_file: str | None = None,
        session_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.target = target
        self.credentials = credentials
        self.timeout = timeout
        self.command_timeout = command_timeout
        self.ssh_config_file = ssh_config_file
        self.session_factory = session_factory if session_factory is not None else ConnectHandler
        self._session: Any | None = None

    def _normalize_command(self, command: str) -> str:
        if any(c in command for c in ("\n", "\r", ";", "|")):
            raise CommandNotAllowedError(
                f"Command contains forbidden characters: {command!r}",
                host=self.target.host,
            )

        cmd_clean = " ".join(command.strip().split()).lower()

        for prefix in ("conf", "write", "reload", "copy", "delete"):
            if cmd_clean.startswith(prefix):
                raise CommandNotAllowedError(
                    f"Configuration or destructive commands are forbidden: {command!r}",
                    host=self.target.host,
                )

        if cmd_clean not in self.ALLOWED_COMMANDS:
            raise CommandNotAllowedError(
                f"Command not in allowlist: {command!r}",
                host=self.target.host,
            )

        return cmd_clean

    def connect(self) -> None:
        if self._session is not None:
            return

        logger.debug(
            "Connecting to device %s at %s:%d",
            self.target.device_id,
            self.target.host,
            self.target.port,
        )

        device_params: dict[str, Any] = {
            "device_type": "cisco_ios",
            "host": self.target.host,
            "port": self.target.port,
            "username": self.credentials.username,
            "password": self.credentials.password,
            "conn_timeout": self.timeout,
            "banner_timeout": self.timeout,
            "auth_timeout": self.timeout,
            "use_keys": False,
            "allow_agent": False,
        }

        if self.credentials.enable_secret is not None:
            device_params["secret"] = self.credentials.enable_secret

        if self.ssh_config_file is not None and os.path.isfile(self.ssh_config_file):
            device_params["ssh_config_file"] = self.ssh_config_file

        try:
            session = self.session_factory(**device_params)
            try:
                prompt = session.find_prompt()
                if prompt.strip().endswith(">"):
                    if self.credentials.enable_secret:
                        try:
                            session.enable()
                        except ValueError as exc:
                            raise AuthenticationFailedError(
                                f"Enable mode authentication failed for {self.target.host}:{self.target.port}",
                                host=self.target.host,
                            ) from exc
                    else:
                        raise ConfigCollectionError(
                            "Privileged EXEC mode required but no enable secret was provided",
                            host=self.target.host,
                        )

                self._session = session
            except Exception:
                try:
                    session.disconnect()
                except Exception as e:
                    logger.debug("Error disconnecting session during cleanup: %s", type(e).__name__)
                self._session = None
                raise
        except NetSentryError:
            raise
        except (NetmikoAuthenticationException, paramiko.AuthenticationException) as exc:
            logger.debug("Authentication failed for host %s: %s", self.target.host, type(exc).__name__)
            raise AuthenticationFailedError(
                f"SSH authentication failed for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except (NetmikoTimeoutException, ReadTimeout, TimeoutError, socket.timeout) as exc:
            logger.debug("Connection timed out for host %s: %s", self.target.host, type(exc).__name__)
            raise ConnectionTimeoutError(
                f"Connection timed out for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except (paramiko.SSHException, OSError, EOFError) as exc:
            logger.debug("SSH connection failed for host %s: %s", self.target.host, type(exc).__name__)
            raise ConnectionFailedError(
                f"SSH connection failed for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except NetmikoBaseException as exc:
            logger.debug("Netmiko connection error for host %s: %s", self.target.host, type(exc).__name__)
            raise ConfigCollectionError(
                f"Netmiko error occurred for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc

    def _run(self, command: str) -> str:
        cmd_clean = self._normalize_command(command)

        if self._session is None:
            raise ConnectionFailedError("Not connected", host=self.target.host)

        logger.debug(
            "Executing command '%s' on %s (%s)",
            cmd_clean,
            self.target.device_id,
            self.target.host,
        )

        try:
            output = self._session.send_command(cmd_clean, read_timeout=self.command_timeout)
        except NetSentryError:
            raise
        except (NetmikoAuthenticationException, paramiko.AuthenticationException) as exc:
            logger.debug("Authentication error on host %s: %s", self.target.host, type(exc).__name__)
            raise AuthenticationFailedError(
                f"SSH authentication failed for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except (NetmikoTimeoutException, ReadTimeout, TimeoutError, socket.timeout) as exc:
            logger.debug("Command execution timed out for host %s: %s", self.target.host, type(exc).__name__)
            raise ConnectionTimeoutError(
                f"Command execution timed out for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except (paramiko.SSHException, OSError, EOFError) as exc:
            logger.debug("SSH connection failed during command execution on host %s: %s", self.target.host, type(exc).__name__)
            raise ConnectionFailedError(
                f"SSH connection failed for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except NetmikoBaseException as exc:
            logger.debug("Netmiko command error on host %s: %s", self.target.host, type(exc).__name__)
            raise ConfigCollectionError(
                f"Failed to execute command on {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc

        if not output or not output.strip():
            raise ConfigCollectionError(
                f"Empty output received for command {command!r}",
                host=self.target.host,
            )

        non_empty_lines = [line.strip() for line in output.splitlines() if line.strip()]
        if non_empty_lines:
            first_line = non_empty_lines[0]
            for marker in ("% Invalid input", "% Authorization failed", "% Ambiguous command", "% Incomplete command"):
                if marker in first_line:
                    raise ConfigCollectionError(
                        f"IOS command error: {marker}",
                        host=self.target.host,
                    )

        return output

    def get_running_config(self) -> str:
        return self._run("show running-config")

    def get_hostname(self) -> str:
        if self._session is None:
            raise ConnectionFailedError("Not connected", host=self.target.host)

        try:
            prompt = self._session.find_prompt()
            return prompt.strip().rstrip("#>").strip()
        except NetSentryError:
            raise
        except (NetmikoAuthenticationException, paramiko.AuthenticationException) as exc:
            logger.debug("Authentication failed for host %s: %s", self.target.host, type(exc).__name__)
            raise AuthenticationFailedError(
                f"SSH authentication failed for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except (NetmikoTimeoutException, ReadTimeout, TimeoutError, socket.timeout) as exc:
            logger.debug("Hostname prompt timeout on %s: %s", self.target.host, type(exc).__name__)
            raise ConnectionTimeoutError(
                f"Connection timed out for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except (paramiko.SSHException, OSError, EOFError) as exc:
            logger.debug("SSH connection failed while retrieving hostname on %s: %s", self.target.host, type(exc).__name__)
            raise ConnectionFailedError(
                f"SSH connection failed for {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc
        except NetmikoBaseException as exc:
            logger.debug("Netmiko hostname error on %s: %s", self.target.host, type(exc).__name__)
            raise ConfigCollectionError(
                f"Failed to retrieve hostname on {self.target.host}:{self.target.port}",
                host=self.target.host,
            ) from exc

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.disconnect()
            except Exception as exc:
                logger.debug("Error disconnecting from host %s: %s", self.target.host, type(exc).__name__)
            finally:
                self._session = None

    def __repr__(self) -> str:
        return (
            f"CiscoIOSConnector(device_id={self.target.device_id!r}, "
            f"host={self.target.host!r}, port={self.target.port!r})"
        )
