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
    # New auth & public mode settings
    public_mode: bool = False
    api_key_auth: bool = True
    session_cookie_secure: bool = True
    session_ttl_minutes: int = 480
    session_idle_minutes: int = 30
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    login_rate_limit: str = "10/300"
    trusted_ip_header: str | None = None
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "*.trycloudflare.com")
    allow_body_credentials: bool = True
    serve_frontend: bool = False
    frontend_dist: Path | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = environ if environ is not None else os.environ

        repo_root = Path(__file__).resolve().parent.parent.parent.parent

        # Public mode check
        public_mode_raw = env.get("NETSENTRY_PUBLIC_MODE", "0").strip().lower()
        public_mode = public_mode_raw in ("1", "true", "yes")

        # 1. NETSENTRY_AUTH_DISABLED
        auth_disabled_raw = env.get("NETSENTRY_AUTH_DISABLED", "0").strip().lower()
        auth_disabled = auth_disabled_raw in ("1", "true", "yes")
        if public_mode and auth_disabled:
            raise RuntimeError("NETSENTRY_AUTH_DISABLED=1 is strictly forbidden when NETSENTRY_PUBLIC_MODE=1")

        # 2. NETSENTRY_API_KEY & API Key Auth
        api_key = env.get("NETSENTRY_API_KEY")
        api_key_auth_raw = env.get("NETSENTRY_API_KEY_AUTH", "1").strip().lower()
        api_key_auth = api_key_auth_raw in ("1", "true", "yes")

        # Public mode forces API key auth off
        if public_mode:
            api_key_auth = False

        if not auth_disabled and api_key_auth:
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

        if public_mode and not allowed_networks:
            raise RuntimeError("NETSENTRY_ALLOWED_NETWORKS cannot be empty in public mode (SSRF protection)")

        # 6. NETSENTRY_ENABLE_DOCS
        if public_mode:
            enable_docs = False
        else:
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

        # 8. Session settings
        if public_mode:
            session_cookie_secure = True
        else:
            cookie_sec_raw = env.get("NETSENTRY_SESSION_COOKIE_SECURE", "1").strip().lower()
            session_cookie_secure = cookie_sec_raw in ("1", "true", "yes")

        session_ttl = int(env.get("NETSENTRY_SESSION_TTL_MINUTES", "480"))
        session_idle = int(env.get("NETSENTRY_SESSION_IDLE_MINUTES", "30"))
        max_failed = int(env.get("NETSENTRY_MAX_FAILED_LOGINS", "5"))
        lockout_min = int(env.get("NETSENTRY_LOCKOUT_MINUTES", "15"))
        login_rate_limit = env.get("NETSENTRY_LOGIN_RATE_LIMIT", "10/300").strip()

        # 9. Trusted IP header & Allowed Hosts
        trusted_ip_header = env.get("NETSENTRY_TRUSTED_IP_HEADER", "").strip() or None

        allowed_hosts_raw = env.get(
            "NETSENTRY_ALLOWED_HOSTS",
            "localhost,127.0.0.1,*.trycloudflare.com",
        ).strip()
        allowed_hosts = tuple(h.strip() for h in allowed_hosts_raw.split(",") if h.strip())

        # 10. Body credentials
        if public_mode:
            allow_body_credentials = False
        else:
            body_creds_raw = env.get("NETSENTRY_ALLOW_BODY_CREDENTIALS", "1").strip().lower()
            allow_body_credentials = body_creds_raw in ("1", "true", "yes")

        # 11. Serve frontend & static dist
        serve_frontend_raw = env.get("NETSENTRY_SERVE_FRONTEND", "0").strip().lower()
        serve_frontend = serve_frontend_raw in ("1", "true", "yes")

        dist_raw = env.get("NETSENTRY_FRONTEND_DIST")
        if dist_raw:
            frontend_dist = Path(dist_raw)
        else:
            frontend_dist = repo_root / "frontend" / "dist"

        return cls(
            db_path=db_path,
            api_key=api_key,
            auth_disabled=auth_disabled,
            cors_origins=cors_origins,
            allowed_networks=allowed_networks,
            enable_docs=enable_docs,
            default_credentials=default_credentials,
            public_mode=public_mode,
            api_key_auth=api_key_auth,
            session_cookie_secure=session_cookie_secure,
            session_ttl_minutes=session_ttl,
            session_idle_minutes=session_idle,
            max_failed_logins=max_failed,
            lockout_minutes=lockout_min,
            login_rate_limit=login_rate_limit,
            trusted_ip_header=trusted_ip_header,
            allowed_hosts=allowed_hosts,
            allow_body_credentials=allow_body_credentials,
            serve_frontend=serve_frontend,
            frontend_dist=frontend_dist,
        )
