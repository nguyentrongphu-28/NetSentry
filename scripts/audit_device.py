#!/usr/bin/env python3
"""NetSentry CLI script to audit a live network device via SSH."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
from pathlib import Path
import sys

# Silence verbose third-party logs immediately
logging.getLogger("netmiko").setLevel(logging.WARNING)
logging.getLogger("paramiko").setLevel(logging.WARNING)

# Ensure backend/ and scripts/ are in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _table import print_findings_table  # noqa: E402
from app.domain.entities.audit_result import AuditStatus  # noqa: E402
from app.domain.entities.device import Credentials, DeviceTarget  # noqa: E402
from app.factories.connector_factory import build_default_connector_factory  # noqa: E402
from app.rules.registry import build_default_engine  # noqa: E402
from app.services.audit_service import AuditService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit a network device configuration against NetSentry rules via SSH.",
    )
    parser.add_argument(
        "--host",
        required=True,
        type=str,
        help="Device IP address or hostname to connect to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=22,
        help="SSH port (default: 22).",
    )
    parser.add_argument(
        "--device-id",
        type=str,
        default=None,
        help="Identifier for the device (defaults to host).",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="cisco_ios",
        help="Device platform connector (default: cisco_ios).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output findings in JSON format.",
    )
    parser.add_argument(
        "--dump-config",
        type=Path,
        default=None,
        help="Path inside data/raw_configs/ to save the raw running configuration.",
    )
    return parser.parse_args()


def get_credentials() -> Credentials | None:
    username = os.environ.get("NETSENTRY_SSH_USERNAME")
    password = os.environ.get("NETSENTRY_SSH_PASSWORD")
    enable_secret = os.environ.get("NETSENTRY_ENABLE_SECRET")

    is_interactive = sys.stdin.isatty()

    if not username and is_interactive:
        try:
            username = input("SSH username: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            return None

    if not password and is_interactive:
        try:
            password = getpass.getpass("SSH password: ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            return None

    if not username:
        print(
            "Error: SSH username is required (set NETSENTRY_SSH_USERNAME or run interactively).",
            file=sys.stderr,
        )
        return None

    if not password:
        print(
            "Error: SSH password is required (set NETSENTRY_SSH_PASSWORD or run interactively).",
            file=sys.stderr,
        )
        return None

    try:
        return Credentials(
            username=username,
            password=password,
            enable_secret=enable_secret if enable_secret else None,
        )
    except ValueError as exc:
        print(f"Error: Invalid credentials - {exc}", file=sys.stderr)
        return None


def main() -> int:
    args = parse_args()

    credentials = get_credentials()
    if credentials is None:
        return 1

    device_id = args.device_id or args.host
    try:
        target = DeviceTarget(
            device_id=device_id,
            host=args.host,
            platform=args.platform,
            port=args.port,
        )
    except ValueError as exc:
        print(f"Error: Invalid target parameters - {exc}", file=sys.stderr)
        return 1

    dump_callback = None
    if args.dump_config is not None:
        raw_configs_dir = (REPO_ROOT / "data" / "raw_configs").resolve()
        raw_configs_dir.mkdir(parents=True, exist_ok=True)

        target_file = args.dump_config.resolve()
        try:
            target_file.relative_to(raw_configs_dir)
        except ValueError:
            print(
                f"Error: --dump-config path must be inside '{raw_configs_dir}' to prevent path traversal.",
                file=sys.stderr,
            )
            return 1

        def _dump_hook(config_text: str) -> None:
            print("Warning: Raw config may contain secrets. Keep it out of Git.", file=sys.stderr)
            try:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(config_text, encoding="utf-8")
                try:
                    os.chmod(target_file, 0o600)
                except OSError:
                    pass
                print(f"Raw configuration saved to {target_file}")
            except Exception as e:
                print(f"Error saving raw configuration to {target_file}: {e}", file=sys.stderr)

        dump_callback = _dump_hook

    factory = build_default_connector_factory()
    engine = build_default_engine()
    service = AuditService(connector_factory=factory, engine=engine)

    result = service.audit_device(target, credentials, on_config_collected=dump_callback)

    if result.status == AuditStatus.FAILED:
        print(
            f"Error: [{result.error_code}] {result.error_message}",
            file=sys.stderr,
        )
        return 2

    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        title = result.hostname or result.device_id
        print_findings_table(result.findings, result.device_id, title)

    return 0


if __name__ == "__main__":
    sys.exit(main())
