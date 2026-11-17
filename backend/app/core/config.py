"""Application settings and environment configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
from ipaddress import IPv4Network, IPv6Network
import os
from pathlib import Path
from typing import Mapping

from app.domain.entities.device import Credentials


class ConfigError(Exception):
    """Raised when application configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    db_path: Path
    api_key: str | None = field(repr=False)
    auth_disabled: bool
    cors_origins: tuple[str, ...]
    allowed_networks: tuple[IPv4Network | IPv6Network, ...]
    enable_docs: bool
    default_credentials: Credentials | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = environ if environ is not None else os.environ

        # 1. NETSENTRY_AUTH_DISABLED
        auth_disabled_raw = env.get("NETSENTRY_AUTH_DISABLED", "0").strip().lower()
        auth_disabled = auth_disabled_raw in ("1", "true", "yes")

        # 2. NETSENTRY_API_KEY
        api_key = env.get("NETSENTRY_API_KEY")
        if not auth_disabled:
            if not api_key:
                raise ConfigError("NETSENTRY_API_KEY environment variable is required")
            if len(api_key) < 16:
                raise ConfigError(
                    f"NETSENTRY_API_KEY must be at least 16 characters long (got {len(api_key)})"
                )

        # 3. NETSENTRY_DB_PATH
        db_path_raw = env.get("NETSENTRY_DB_PATH")
        if db_path_raw:
            db_path = Path(db_path_raw)
        else:
            # Default: <repo>/data/netsentry.db
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            db_path = repo_root / "data" / "netsentry.db"

        # 4. NETSENTRY_CORS_ORIGINS
        cors_raw = env.get("NETSENTRY_CORS_ORIGINS", "").strip()
        if cors_raw:
            cors_origins = tuple(o.strip() for o in cors_raw.split(",") if o.strip())
        else:
            cors_origins = ()

        # 5. NETSENTRY_ALLOWED_NETWORKS
        networks_raw = env.get("NETSENTRY_ALLOWED_NETWORKS", "").strip()
        allowed_networks_list: list[IPv4Network | IPv6Network] = []
        if networks_raw:
            for net_str in networks_raw.split(","):
                net_str = net_str.strip()
                if not net_str:
                    continue
                try:
                    allowed_networks_list.append(ipaddress.ip_network(net_str, strict=False))
                except ValueError as exc:
                    raise ConfigError(f"Invalid CIDR network '{net_str}': {exc}") from exc
        allowed_networks = tuple(allowed_networks_list)

        # 6. NETSENTRY_ENABLE_DOCS
        docs_raw = env.get("NETSENTRY_ENABLE_DOCS", "1").strip().lower()
        enable_docs = docs_raw not in ("0", "false", "no")

        # 7. Fallback SSH credentials
        ssh_user = env.get("NETSENTRY_SSH_USERNAME")
        ssh_pw = env.get("NETSENTRY_SSH_PASSWORD")
        ssh_enable = env.get("NETSENTRY_ENABLE_SECRET") or env.get("NETSENTRY_SSH_ENABLE_SECRET")

        default_credentials: Credentials | None = None
        if ssh_user and ssh_pw:
            default_credentials = Credentials(
                username=ssh_user,
                password=ssh_pw,
                enable_secret=ssh_enable,
            )

        return cls(
            db_path=db_path,
            api_key=api_key,
            auth_disabled=auth_disabled,
            cors_origins=cors_origins,
            allowed_networks=allowed_networks,
            enable_docs=enable_docs,
            default_credentials=default_credentials,
        )
