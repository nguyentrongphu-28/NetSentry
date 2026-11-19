"""Client IP resolution logic without framework dependencies."""

from __future__ import annotations

import ipaddress

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def resolve_client_ip(
    peer_host: str | None,
    header_value: str | None = None,
    trusted_header_configured: str | None = None,
) -> str:
    """Resolve client IP safely.

    Strict Security Constraints:
    - Only trust header_value if trusted_header_configured is non-empty AND peer_host is a loopback address.
    - If peer_host is not loopback, NEVER trust header_value (prevents IP spoofing).
    - If header_value contains multiple comma-separated IPs, take the first valid IP.
    - Validate IP format with ipaddress module; fallback to peer_host if invalid.
    """
    default_host = peer_host or "127.0.0.1"

    if not trusted_header_configured or not header_value:
        return default_host

    # Verify if peer is loopback
    is_loopback = False
    if peer_host in LOOPBACK_HOSTS:
        is_loopback = True
    elif peer_host:
        try:
            ip_obj = ipaddress.ip_address(peer_host)
            if ip_obj.is_loopback:
                is_loopback = True
        except ValueError:
            is_loopback = False

    if not is_loopback:
        return default_host

    # Extract first IP from header
    candidate = header_value.split(",")[0].strip()
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        return default_host
