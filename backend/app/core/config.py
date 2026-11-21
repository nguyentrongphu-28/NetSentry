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
    # Snapshot configuration
    snapshot_enabled: bool = True
    snapshot_dir: Path | None = None
    snapshot_keep: int = 30
    snapshot_hmac_key: str = ""
    snapshot_content_api: bool = True
    # AI configuration
    ai_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_allow_remote: bool = False
    ollama_model: str = "qwen2.5:7b-instruct"
    ai_timeout_seconds: int = 120
    ai_max_concurrency: int = 1
    ai_rate_limit: str = "5/3600"
    # Baseline & Drift configuration
    baseline_enabled: bool = True
    drift_max_blocks: int = 500
    # Remediation configuration
    remediation_enabled: bool = False
    remediation_proposal_ttl_minutes: int = 120
    remediation_approval_ttl_minutes: int = 60
    remediation_max_audit_age_minutes: int = 60
    remediation_require_distinct_approver: bool = True

    def __post_init__(self) -> None:
        if self.public_mode:
            # Enforce public mode constraints
            object.__setattr__(self, "snapshot_content_api", False)
            object.__setattr__(self, "allow_body_credentials", False)
            object.__setattr__(self, "api_key_auth", False)
            object.__setattr__(self, "ollama_allow_remote", False)
            object.__setattr__(self, "remediation_require_distinct_approver", True)

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

        # 12. Snapshot settings
        snapshot_enabled_raw = env.get("NETSENTRY_SNAPSHOT_ENABLED", "1").strip().lower()
        snapshot_enabled = snapshot_enabled_raw in ("1", "true", "yes")

        snapshot_dir_raw = env.get("NETSENTRY_SNAPSHOT_DIR")
        if snapshot_dir_raw:
            snapshot_dir = Path(snapshot_dir_raw)
        else:
            snapshot_dir = repo_root / "data" / "snapshots"

        try:
            snapshot_keep = int(env.get("NETSENTRY_SNAPSHOT_KEEP", "30"))
            if not (1 <= snapshot_keep <= 500):
                raise ConfigError("NETSENTRY_SNAPSHOT_KEEP must be between 1 and 500")
        except ValueError as exc:
            raise ConfigError(f"Invalid NETSENTRY_SNAPSHOT_KEEP: {exc}") from exc

        snapshot_hmac_key = env.get("NETSENTRY_SNAPSHOT_HMAC_KEY", "").strip()

        if public_mode:
            snapshot_content_api = False
        else:
            content_api_raw = env.get("NETSENTRY_SNAPSHOT_CONTENT_API", "1").strip().lower()
            snapshot_content_api = content_api_raw in ("1", "true", "yes")

        # 13. AI settings
        ai_enabled_raw = env.get("NETSENTRY_AI_ENABLED", "0").strip().lower()
        ai_enabled = ai_enabled_raw in ("1", "true", "yes")

        ollama_url = env.get("NETSENTRY_OLLAMA_URL", "http://127.0.0.1:11434").strip()
        allow_remote_raw = env.get("NETSENTRY_OLLAMA_ALLOW_REMOTE", "0").strip().lower()
        ollama_allow_remote = allow_remote_raw in ("1", "true", "yes")

        if ai_enabled:
            # Check loopback
            from urllib.parse import urlparse
            parsed_ollama = urlparse(ollama_url)
            host = (parsed_ollama.hostname or "").lower()
            is_loopback = host in ("127.0.0.1", "localhost", "::1")
            if public_mode:
                if not is_loopback or ollama_allow_remote:
                    raise RuntimeError("In public mode with AI enabled, NETSENTRY_OLLAMA_URL must be loopback and remote is forbidden")
            elif not is_loopback and not ollama_allow_remote:
                raise ConfigError(f"NETSENTRY_OLLAMA_URL host '{host}' is not loopback. Set NETSENTRY_OLLAMA_ALLOW_REMOTE=1 if intentional.")

        ollama_model = env.get("NETSENTRY_OLLAMA_MODEL", "qwen2.5:7b-instruct").strip()

        try:
            ai_timeout_seconds = int(env.get("NETSENTRY_AI_TIMEOUT_SECONDS", "120"))
            if not (10 <= ai_timeout_seconds <= 600):
                raise ConfigError("NETSENTRY_AI_TIMEOUT_SECONDS must be between 10 and 600")
        except ValueError as exc:
            raise ConfigError(f"Invalid NETSENTRY_AI_TIMEOUT_SECONDS: {exc}") from exc

        try:
            ai_max_concurrency = int(env.get("NETSENTRY_AI_MAX_CONCURRENCY", "1"))
            if ai_max_concurrency < 1:
                raise ConfigError("NETSENTRY_AI_MAX_CONCURRENCY must be at least 1")
        except ValueError as exc:
            raise ConfigError(f"Invalid NETSENTRY_AI_MAX_CONCURRENCY: {exc}") from exc

        ai_rate_limit = env.get("NETSENTRY_AI_RATE_LIMIT", "5/3600").strip()

        # Baseline configuration
        baseline_enabled_raw = env.get("NETSENTRY_BASELINE_ENABLED", "1").strip().lower()
        baseline_enabled = baseline_enabled_raw in ("1", "true", "yes")

        if not snapshot_enabled and baseline_enabled:
            import logging
            logging.getLogger(__name__).warning(
                "NETSENTRY_BASELINE_ENABLED=1 but NETSENTRY_SNAPSHOT_ENABLED=0. Forcing baseline_enabled=False."
            )
            baseline_enabled = False

        try:
            drift_max_blocks = int(env.get("NETSENTRY_DRIFT_MAX_BLOCKS", "500"))
            if not (1 <= drift_max_blocks <= 5000):
                raise ConfigError("NETSENTRY_DRIFT_MAX_BLOCKS must be between 1 and 5000")
        except ValueError as exc:
            raise ConfigError(f"Invalid NETSENTRY_DRIFT_MAX_BLOCKS: {exc}") from exc

        # Remediation configuration
        remediation_enabled_raw = env.get("NETSENTRY_REMEDIATION_ENABLED", "0").strip().lower()
        remediation_enabled = remediation_enabled_raw in ("1", "true", "yes")

        try:
            remediation_proposal_ttl_minutes = int(env.get("NETSENTRY_REMEDIATION_PROPOSAL_TTL_MINUTES", "120"))
            if not (5 <= remediation_proposal_ttl_minutes <= 1440):
                raise ConfigError("NETSENTRY_REMEDIATION_PROPOSAL_TTL_MINUTES must be between 5 and 1440")
        except ValueError as exc:
            raise ConfigError(f"Invalid NETSENTRY_REMEDIATION_PROPOSAL_TTL_MINUTES: {exc}") from exc

        try:
            remediation_approval_ttl_minutes = int(env.get("NETSENTRY_REMEDIATION_APPROVAL_TTL_MINUTES", "60"))
            if not (5 <= remediation_approval_ttl_minutes <= 1440):
                raise ConfigError("NETSENTRY_REMEDIATION_APPROVAL_TTL_MINUTES must be between 5 and 1440")
        except ValueError as exc:
            raise ConfigError(f"Invalid NETSENTRY_REMEDIATION_APPROVAL_TTL_MINUTES: {exc}") from exc

        try:
            remediation_max_audit_age_minutes = int(env.get("NETSENTRY_REMEDIATION_MAX_AUDIT_AGE_MINUTES", "60"))
            if not (1 <= remediation_max_audit_age_minutes <= 1440):
                raise ConfigError("NETSENTRY_REMEDIATION_MAX_AUDIT_AGE_MINUTES must be between 1 and 1440")
        except ValueError as exc:
            raise ConfigError(f"Invalid NETSENTRY_REMEDIATION_MAX_AUDIT_AGE_MINUTES: {exc}") from exc

        remediation_require_distinct_approver_raw = env.get("NETSENTRY_REMEDIATION_REQUIRE_DISTINCT_APPROVER", "1").strip().lower()
        remediation_require_distinct_approver = remediation_require_distinct_approver_raw in ("1", "true", "yes")
        if public_mode:
            remediation_require_distinct_approver = True

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
            snapshot_enabled=snapshot_enabled,
            snapshot_dir=snapshot_dir,
            snapshot_keep=snapshot_keep,
            snapshot_hmac_key=snapshot_hmac_key,
            snapshot_content_api=snapshot_content_api,
            ai_enabled=ai_enabled,
            ollama_url=ollama_url,
            ollama_allow_remote=ollama_allow_remote,
            ollama_model=ollama_model,
            ai_timeout_seconds=ai_timeout_seconds,
            ai_max_concurrency=ai_max_concurrency,
            ai_rate_limit=ai_rate_limit,
            baseline_enabled=baseline_enabled,
            drift_max_blocks=drift_max_blocks,
            remediation_enabled=remediation_enabled,
            remediation_proposal_ttl_minutes=remediation_proposal_ttl_minutes,
            remediation_approval_ttl_minutes=remediation_approval_ttl_minutes,
            remediation_max_audit_age_minutes=remediation_max_audit_age_minutes,
            remediation_require_distinct_approver=remediation_require_distinct_approver,
        )
