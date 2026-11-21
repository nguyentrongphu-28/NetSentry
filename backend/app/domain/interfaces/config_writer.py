"""Domain interfaces for device configuration writers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class CommandExecutionResult:
    command: str
    accepted: bool
    output_excerpt: str  # sanitized, <= 200 chars


@dataclass(frozen=True, slots=True)
class WriteResult:
    success: bool
    commands: tuple[CommandExecutionResult, ...]
    failure_reason: str | None = None


class ConfigWriter(Protocol):
    """Protocol for safely applying configuration changes to a network device."""

    def __enter__(self) -> "ConfigWriter": ...

    def __exit__(self, *exc) -> None: ...

    def apply(
        self,
        commands: Sequence[str],
        *,
        is_rollback: bool = False,
    ) -> WriteResult:
        """Apply a sequence of commands one by one in configuration mode.

        Validates all commands before execution.
        Raises WriteRejectedError, WriteAuthFailedError, or WriteConnectionError on failure.
        """
        ...

    def save_config(self) -> None:
        """Persist running configuration to startup configuration (write memory)."""
        ...


class ConfigWriterFactory(Protocol):
    """Factory interface for creating ConfigWriter instances."""

    def create_writer(
        self,
        device_id: str,
        host: str,
        port: int,
        platform: str,
    ) -> ConfigWriter: ...
