"""Fake configuration writer for unit and integration testing without network calls."""

from __future__ import annotations

from typing import Any, Sequence

from app.domain.errors import (
    CommandNotAllowedError,
    WriteConnectionError,
    WriteRejectedError,
)
from app.domain.interfaces.config_writer import (
    CommandExecutionResult,
    ConfigWriter,
    ConfigWriterFactory,
    WriteResult,
)
from app.remediation.command_policy import (
    validate_commands,
    validate_rollback_commands,
)


class FakeConfigWriter(ConfigWriter):
    """ConfigWriter test double verifying zero device touch in dry-run and recording commands."""

    def __init__(
        self,
        *,
        raise_if_called: bool = False,
        fail_at_command_index: int | None = None,
        fail_exception: Exception | None = None,
        fail_on_save: bool = False,
        fail_save_exception: Exception | None = None,
    ) -> None:
        self.raise_if_called = raise_if_called
        self.fail_at_command_index = fail_at_command_index
        self.fail_exception = fail_exception
        self.fail_on_save = fail_on_save
        self.fail_save_exception = fail_save_exception

        self.applied_commands: list[str] = []
        self.rollback_commands: list[str] = []
        self.save_config_called: bool = False
        self.is_connected: bool = False

    def __enter__(self) -> FakeConfigWriter:
        if self.raise_if_called:
            raise RuntimeError("FakeConfigWriter.__enter__ was called but raise_if_called=True!")
        self.is_connected = True
        return self

    def __exit__(self, *exc: Any) -> None:
        self.is_connected = False

    def apply(
        self,
        commands: Sequence[str],
        *,
        is_rollback: bool = False,
    ) -> WriteResult:
        if self.raise_if_called:
            raise RuntimeError("FakeConfigWriter.apply was called but raise_if_called=True!")

        results: list[CommandExecutionResult] = []
        for idx, cmd in enumerate(commands):
            # Validate commands beforehand
            if is_rollback:
                try:
                    validate_rollback_commands((cmd,))
                except ValueError as exc:
                    raise CommandNotAllowedError(f"Invalid rollback command: {cmd}") from exc
            else:
                try:
                    validate_commands((cmd,))
                except ValueError as exc:
                    raise CommandNotAllowedError(f"Invalid remediation command: {cmd}") from exc

            # Inject failure if programmed
            if self.fail_at_command_index is not None and idx == self.fail_at_command_index:
                err = self.fail_exception or WriteRejectedError(f"Simulated rejection at index {idx} for {cmd!r}")
                results.append(
                    CommandExecutionResult(
                        command=cmd,
                        accepted=False,
                        output_excerpt=f"% Error executing {cmd}",
                    )
                )
                raise err

            if is_rollback:
                self.rollback_commands.append(cmd)
            else:
                self.applied_commands.append(cmd)

            results.append(
                CommandExecutionResult(
                    command=cmd,
                    accepted=True,
                    output_excerpt="OK",
                )
            )

        return WriteResult(success=True, commands=tuple(results))

    def save_config(self) -> None:
        if self.raise_if_called:
            raise RuntimeError("FakeConfigWriter.save_config was called but raise_if_called=True!")

        self.save_config_called = True
        if self.fail_on_save:
            raise self.fail_save_exception or WriteRejectedError("Simulated save_config failure")


class FakeConfigWriterFactory(ConfigWriterFactory):
    """Factory creating FakeConfigWriter instances for testing."""

    def __init__(self, writer: FakeConfigWriter | None = None) -> None:
        self.writer = writer or FakeConfigWriter()
        self.created_writers: list[FakeConfigWriter] = []

    def create_writer(
        self,
        device_id: str,
        host: str,
        port: int,
        platform: str,
    ) -> ConfigWriter:
        self.created_writers.append(self.writer)
        return self.writer
