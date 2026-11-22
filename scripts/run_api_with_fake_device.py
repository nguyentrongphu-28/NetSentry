#!/usr/bin/env python3
"""
NetSentry - Dev-only API server with fake Cisco IOS device connector.
Loads a mock configuration fixture instead of connecting over SSH to real devices.
DO NOT USE IN PRODUCTION.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
import tempfile
from pathlib import Path

# Add backend to path so we can import app
repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import uvicorn
from app.connectors.fake_connector import FakeConnector
from app.core.config import Settings
from app.domain.entities.device import DeviceTarget, Credentials
from app.domain.errors import (
    AuthenticationFailedError,
    ConnectionTimeoutError,
    ConnectionFailedError,
    ConfigCollectionError,
)
from app.factories.connector_factory import ConnectorFactory
from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run NetSentry API with a fake Cisco IOS device connector for frontend development."
    )
    parser.add_argument(
        "--fixture",
        choices=["insecure", "secure", "minimal", "banner_trap"],
        default="insecure",
        help="Fixture config file to load (default: insecure)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (must be 127.0.0.1)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Custom API key (if omitted, a random 32-char key is generated)",
    )
    parser.add_argument(
        "--fail-on",
        choices=["auth", "timeout", "connect", "collection"],
        default=None,
        help="Simulate connector failure during audit (auth|timeout|connect|collection)",
    )
    args = parser.parse_args()

    if args.host != "127.0.0.1":
        print("Error: Dev server can only bind to 127.0.0.1 for security.", file=sys.stderr)
        sys.exit(1)

    # Generate or use provided API key (min 16 chars)
    api_key = args.api_key or secrets.token_urlsafe(24)

    # Set mock fallback credentials in environment (dynamically generated per dev run)
    dev_ssh_pass = secrets.token_urlsafe(16)
    dev_enable_sec = secrets.token_urlsafe(16)
    os.environ["NETSENTRY_SSH_USERNAME"] = "dev_admin"
    os.environ["NETSENTRY_SSH_PASSWORD"] = dev_ssh_pass
    os.environ["NETSENTRY_ENABLE_SECRET"] = dev_enable_sec

    # Locate fixture config
    fixture_filename = f"ios_{args.fixture}.cfg"
    fixture_path = backend_dir / "tests" / "fixtures" / "configs" / fixture_filename
    if not fixture_path.exists():
        print(f"Error: Fixture file not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    config_text = fixture_path.read_text(encoding="utf-8")

    # Map simulated connector failure
    fail_on_map = {
        "auth": AuthenticationFailedError,
        "timeout": ConnectionTimeoutError,
        "connect": ConnectionFailedError,
        "collection": ConfigCollectionError,
    }
    fail_on_cls = fail_on_map.get(args.fail_on) if args.fail_on else None

    # Create temporary SQLite database
    temp_dir = tempfile.mkdtemp(prefix="netsentry_dev_")
    db_path = Path(temp_dir) / "netsentry_dev.db"

    # Configure settings
    default_creds = Credentials(
        username="dev_admin",
        password=dev_ssh_pass,
        enable_secret=dev_enable_sec,
    )
    settings = Settings(
        api_key=api_key,
        auth_disabled=False,
        db_path=db_path,
        allowed_networks=(),
        cors_origins=(),
        enable_docs=True,
        default_credentials=default_creds,
    )

    # Build ConnectorFactory with FakeConnector
    def fake_connector_builder(target: DeviceTarget, creds: Credentials) -> FakeConnector:
        return FakeConnector(
            config_text=config_text,
            hostname=f"Host-{target.device_id}",
            fail_on=fail_on_cls,
        )

    connector_factory = ConnectorFactory()
    connector_factory.register("cisco_ios", fake_connector_builder)

    # Create FastAPI app
    app = create_app(settings=settings, connector_factory=connector_factory)

    # Seed initial admin user for session login
    from app.repositories.sqlite_user_repository import SQLiteUserRepository
    from app.security.password_hasher import Argon2PasswordHasher
    from app.domain.entities.user import Role
    user_repo = SQLiteUserRepository(db_path)
    hasher = Argon2PasswordHasher()
    dev_password = secrets.token_urlsafe(16)
    user_repo.add("admin", hasher.hash(dev_password), Role.ADMIN, must_change_password=False)

    banner = "=" * 70
    print(banner)
    print("  NETSENTRY DEV-ONLY API SERVER (MOCK DEVICE CONNECTOR)")
    print("  WARNING: This server uses mock data and in-memory/temp storage.")
    print("  DO NOT USE IN PRODUCTION.")
    print(banner)
    print(f"  * Host / Port      : http://{args.host}:{args.port}")
    print(f"  * Fixture loaded   : {fixture_filename} ({fixture_path})")
    print(f"  * Temp DB path     : {db_path}")
    print(f"  * Web Session Login: admin / {dev_password}")
    print(f"  * Fallback User    : dev_admin")
    print(f"  * Fallback Pass    : {dev_ssh_pass}")
    print(f"  * Generated API Key: {api_key}")
    if fail_on_cls:
        print(f"  * Fail-on Sim      : {args.fail_on} -> {fail_on_cls.__name__}")
    print(banner)
    print("  Log in via web UI or use the API Key in X-API-Key header.\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
