#!/usr/bin/env python3
"""Seed Demo Data Script for NetSentry (Spec Section 8).

Creates standard demo users:
- demo_admin (Role.ADMIN)
- demo_operator (Role.OPERATOR)
- demo_viewer (Role.VIEWER)

Generates one-time random high-entropy passwords (or accepts custom ones),
prints them clearly to terminal, and creates a demo device (Router-Demo-01).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import secrets
import string
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.domain.entities.user import Role
from app.repositories.database import init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher


def generate_random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Ensure at least one uppercase, lowercase, digit, and symbol
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


def seed_demo_data(db_path: Path, reset: bool = False) -> dict[str, str]:
    init_db(db_path)
    user_repo = SQLiteUserRepository(db_path)
    dev_repo = SqliteDeviceRepository(db_path)
    hasher = Argon2PasswordHasher()

    credentials = {}

    users_to_create = [
        ("demo_admin", Role.ADMIN),
        ("demo_operator", Role.OPERATOR),
        ("demo_viewer", Role.VIEWER),
    ]

    for username, role in users_to_create:
        existing = user_repo.get_by_username(username)
        pwd = generate_random_password()
        hashed = hasher.hash(pwd)

        if existing is not None:
            if reset:
                user_repo.update_password(existing.id, hashed)
                credentials[username] = pwd
            else:
                credentials[username] = "(unchanged - already exists)"
        else:
            user_repo.add(username, hashed, role, must_change_password=False)
            credentials[username] = pwd

    # Seed demo device if not exists
    demo_dev = dev_repo.get("Router-Demo-01")
    if demo_dev is None:
        from app.domain.entities.device import Device
        now = datetime.now(timezone.utc)
        dev_repo.add(
            Device(
                device_id="Router-Demo-01",
                name="Demo Lab Gateway Router",
                host="192.168.1.1",
                port=22,
                platform="cisco_ios",
                created_at=now,
                updated_at=now,
            )
        )

    return credentials


def main() -> None:
    parser = argparse.ArgumentParser(description="NetSentry Demo Seeder")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "backend" / "netsentry.db", help="Path to sqlite DB")
    parser.add_argument("--reset", action="store_true", help="Reset passwords of existing demo users")
    args = parser.parse_args()

    print(f"[*] Seeding demo users and device into {args.db}...")
    creds = seed_demo_data(args.db, reset=args.reset)

    print("\n================ DEMO CREDENTIALS ================")
    for u, p in creds.items():
        print(f"  Username: {u:<16} Password: {p}")
    print("===================================================")
    print("Demo Device Created: Router-Demo-01 (192.168.1.1:22, cisco_ios)")
    print("Keep these credentials secure or rotate after the demo.")


if __name__ == "__main__":
    main()
