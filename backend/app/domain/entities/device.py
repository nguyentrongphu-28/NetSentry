"""Domain entities representing devices and connection credentials."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DeviceTarget:
    """Target network device details for connection and auditing."""

    device_id: str
    host: str
    platform: str = "cisco_ios"
    port: int = 22

    def __post_init__(self) -> None:
        if not self.device_id or not self.device_id.strip():
            raise ValueError("device_id must not be empty")
        if not self.host or not self.host.strip():
            raise ValueError("host must not be empty")
        if not (1 <= self.port <= 65535):
            raise ValueError(f"port must be between 1 and 65535, got {self.port}")


@dataclass(frozen=True, slots=True)
class Credentials:
    """SSH authentication credentials."""

    username: str
    password: str = field(repr=False)
    enable_secret: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.username or not self.username.strip():
            raise ValueError("username must not be empty")

    def __str__(self) -> str:
        return repr(self)


# ---------------------------------------------------------------------------
# Persistent Device entity (added in persistence/API phase)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Device:
    """A network device stored in the repository."""

    device_id: str
    name: str
    host: str
    port: int
    platform: str
    created_at: datetime
    updated_at: datetime

    def to_target(self) -> DeviceTarget:
        """Convert to DeviceTarget for use with connectors."""
        return DeviceTarget(
            device_id=self.device_id,
            host=self.host,
            platform=self.platform,
            port=self.port,
        )
