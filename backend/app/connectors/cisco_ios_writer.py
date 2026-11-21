"""Cisco IOS SSH Configuration Writer using Netmiko for automated remediation execution."""

from __future__ import annotations

import logging
import socket
from typing import Any, Callable, Sequence

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoBaseException,
    NetmikoTimeoutException,
    ReadTimeout,
)
import paramiko

from app.domain.errors import (
    CommandNotAllowedError,
    WriteAuthFailedError,
    WriteConnectionError,
    WriteRejectedError,
)
from app.domain.interfaces.config_writer import (
    CommandExecutionResult,
    ConfigWriter,
    WriteResult,
)
from app.remediation.command_policy import (
    validate_commands,
    validate_rollback_commands,
)

logger = logging.getLogger(__name__)

SAVE_CONFIG_COMMAND = "write memory"


def _sanitize_output(raw_output: str, max_length: int = 200) -> str:
    """Sanitize and truncate device output, stripping control chars and excess whitespace."""
    if not raw_output:
        return ""
    cleaned = " ".join(raw_output.strip().split())
    if len(cleaned) > max_length:
        return cleaned[:max_length] + "..."
    return cleaned


class CiscoIOSConfigWriter(ConfigWriter):
    """Configuration writer dedicated exclusively to applying approved remediation commands."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        enable_secret: str = "",
        *,
        timeout: int = 60,
        session_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_secret = enable_secret
        self.timeout = timeout
        self.session_factory = session_factory if session_factory is not None else ConnectHandler
        self._session: Any | None = None

    def __enter__(self) -> CiscoIOSConfigWriter:
        self.connect()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.disconnect()

    def connect(self) -> None:
        """Establish SSH session to Cisco IOS device using dedicated write credentials."""
        if self._session is not None:
            return

        device_params: dict[str, Any] = {
            "device_type": "cisco_ios",
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "secret": self.enable_secret,
            "conn_timeout": self.timeout,
            "banner_timeout": self.timeout,
            "auth_timeout": self.timeout,
            "fast_cli": False,
        }

        try:
            session = self.session_factory(**device_params)
            # Enter privileged mode if secret provided or not already in enable mode
            if self.enable_secret or not session.check_enable_mode():
                session.enable()
            self._session = session
        except NetmikoAuthenticationException as exc:
            logger.warning("Write channel authentication failed for %s:%d", self.host, self.port)
            raise WriteAuthFailedError(f"Write channel authentication failed for {self.host}:{self.port}") from exc
        except (NetmikoTimeoutException, ReadTimeout, socket.timeout) as exc:
            logger.warning("Write channel timeout for %s:%d", self.host, self.port)
            raise WriteConnectionError(f"Write channel timeout for {self.host}:{self.port}") from exc
        except (paramiko.SSHException, socket.error, OSError, EOFError, NetmikoBaseException) as exc:
            logger.warning("Write channel connection error for %s:%d: %s", self.host, self.port, type(exc).__name__)
            raise WriteConnectionError(f"Write channel connection error for {self.host}:{self.port}") from exc

    def disconnect(self) -> None:
        """Disconnect and release session cleanly."""
        if self._session is not None:
            try:
                self._session.disconnect()
            except Exception:
                pass
            finally:
                self._session = None

    def apply(
        self,
        commands: Sequence[str],
        *,
        is_rollback: bool = False,
    ) -> WriteResult:
        """Apply approved commands sequentially in configuration mode."""
        if not commands:
            raise ValueError("No commands provided to apply.")

        # 1. Strict validation of all commands BEFORE touching device
        for cmd in commands:
            try:
                if is_rollback:
                    validate_rollback_commands((cmd,))
                else:
                    validate_commands((cmd,))
            except ValueError as val_err:
                raise CommandNotAllowedError(
                    f"Command validation failed: {cmd!r} - {val_err}",
                    host=self.host,
                ) from val_err

        if self._session is None:
            raise WriteConnectionError("Writer session is not connected.")

        results: list[CommandExecutionResult] = []

        # 2. Enter configuration mode
        try:
            self._session.config_mode()
        except NetmikoAuthenticationException as exc:
            raise WriteAuthFailedError(f"Authentication failed during config_mode: {exc}") from exc
        except (NetmikoTimeoutException, ReadTimeout, socket.timeout) as exc:
            raise WriteConnectionError(f"Timeout entering config mode: {exc}") from exc
        except Exception as exc:
            raise WriteConnectionError(f"Failed entering config mode: {exc}") from exc

        try:
            for cmd in commands:
                try:
                    # Send single command
                    raw_output = self._session.send_config_set(
                        [cmd],
                        enter_config_mode=False,
                        exit_config_mode=False,
                        read_timeout=self.timeout,
                    )
                except (NetmikoTimeoutException, ReadTimeout, socket.timeout) as exc:
                    raise WriteConnectionError(f"Timeout while executing {cmd!r}") from exc
                except Exception as exc:
                    raise WriteConnectionError(f"Connection failure while executing {cmd!r}: {exc}") from exc

                sanitized = _sanitize_output(raw_output)

                # Check if device returned an error indicator (Cisco IOS error messages start with '%')
                lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
                error_lines = [l for l in lines if l.startswith("%")]
                if error_lines:
                    err_msg = error_lines[0]
                    results.append(
                        CommandExecutionResult(
                            command=cmd,
                            accepted=False,
                            output_excerpt=_sanitize_output(err_msg),
                        )
                    )
                    raise WriteRejectedError(f"Device rejected command {cmd!r}: {err_msg}")

                results.append(
                    CommandExecutionResult(
                        command=cmd,
                        accepted=True,
                        output_excerpt=sanitized,
                    )
                )

            return WriteResult(success=True, commands=tuple(results))
        finally:
            # 3. Always exit configuration mode cleanly
            try:
                self._session.exit_config_mode()
            except Exception:
                pass

    def save_config(self) -> None:
        """Execute strictly 'write memory' to persist running-config."""
        if self._session is None:
            raise WriteConnectionError("Writer session is not connected.")

        try:
            output = self._session.send_command(
                SAVE_CONFIG_COMMAND,
                read_timeout=self.timeout,
            )
            # Check for error indicator
            if "%" in output:
                lines = [l.strip() for l in output.splitlines() if l.strip().startswith("%")]
                err_detail = lines[0] if lines else output
                raise WriteRejectedError(f"Save config failed: {_sanitize_output(err_detail)}")
        except (NetmikoTimeoutException, ReadTimeout, socket.timeout) as exc:
            raise WriteConnectionError(f"Timeout during save_config: {exc}") from exc
        except (WriteRejectedError, WriteConnectionError):
            raise
        except Exception as exc:
            raise WriteConnectionError(f"Connection error during save_config: {exc}") from exc
