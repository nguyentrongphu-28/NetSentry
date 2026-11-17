"""Domain service for managing network devices."""

from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
from ipaddress import IPv4Network, IPv6Network
import re
from typing import Callable, Sequence

from app.domain.entities.device import Device
from app.domain.errors import DeviceNotFoundError, InvalidDeviceError
from app.domain.interfaces.device_repository import DeviceRepository

_DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HOSTNAME_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _is_valid_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _is_valid_hostname(host: str) -> bool:
    if not (1 <= len(host) <= 253):
        return False
    for ch in (" ", "/", ":", "@", "?", "#", "\\"):
        if ch in host:
            return False
    labels = host.rstrip(".").split(".")
    if not labels or any(len(label) == 0 for label in labels):
        return False
    return all(_HOSTNAME_LABEL_PATTERN.match(label) for label in labels)


class DeviceService:
    """Business logic and validation for network device entities."""

    def __init__(
        self,
        repository: DeviceRepository,
        *,
        allowed_networks: Sequence[IPv4Network | IPv6Network] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.allowed_networks = tuple(allowed_networks)
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def _validate_device_id(self, device_id: str) -> None:
        if not isinstance(device_id, str) or not _DEVICE_ID_PATTERN.match(device_id):
            raise InvalidDeviceError(
                f"Invalid device_id '{device_id}': must match ^[A-Za-z0-9][A-Za-z0-9._-]{{0,63}}$"
            )

    def _validate_host(self, host: str) -> None:
        if not isinstance(host, str) or not host.strip():
            raise InvalidDeviceError("Host must not be empty")

        ip = _is_valid_ip(host)

        if self.allowed_networks:
            if ip is None:
                raise InvalidDeviceError(
                    f"Host '{host}' is rejected: only IP addresses within allowed networks are permitted"
                )
            if not any(ip in net for net in self.allowed_networks):
                raise InvalidDeviceError(
                    f"Host IP '{host}' is not in any allowed network"
                )
        else:
            if ip is None and not _is_valid_hostname(host):
                raise InvalidDeviceError(f"Host '{host}' is neither a valid IP nor a valid hostname")

    def _validate_port(self, port: int) -> None:
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise InvalidDeviceError(f"Port '{port}' must be between 1 and 65535")

    def _validate_platform(self, platform: str) -> None:
        if platform != "cisco_ios":
            raise InvalidDeviceError(
                f"Platform '{platform}' is unsupported: currently only 'cisco_ios' is accepted"
            )

    def create(
        self,
        device_id: str,
        host: str,
        *,
        name: str | None = None,
        port: int = 22,
        platform: str = "cisco_ios",
    ) -> Device:
        self._validate_device_id(device_id)
        self._validate_host(host)
        self._validate_port(port)
        self._validate_platform(platform)

        final_name = name.strip() if name and name.strip() else device_id
        now = self.clock()

        device = Device(
            device_id=device_id,
            name=final_name,
            host=host,
            port=port,
            platform=platform,
            created_at=now,
            updated_at=now,
        )
        self.repository.add(device)
        return device

    def get(self, device_id: str) -> Device:
        device = self.repository.get(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        return device

    def list(self) -> list[Device]:
        return self.repository.list()

    def delete(self, device_id: str) -> None:
        deleted = self.repository.delete(device_id)
        if not deleted:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
