#!/usr/bin/env python3
"""CLI script to create the initial admin user for NetSentry."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import Settings
from app.domain.entities.user import Role
from app.domain.errors import UserExistsError, WeakPasswordError
from app.repositories.database import init_db
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher
from app.security.password_policy import validate_password_strength


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user for NetSentry.")
    parser.add_argument("--username", required=True, help="Username for the new admin (lowercase letters, numbers, ., _, -)")
    args = parser.parse_args()

    username = args.username.strip().lower()
    if len(username) < 3 or len(username) > 32:
        print("Error: Username must be between 3 and 32 characters long.", file=sys.stderr)
        sys.exit(1)

    print(f"Creating administrator user '{username}'.")
    password = getpass.getpass("Enter password: ")
    confirm_password = getpass.getpass("Confirm password: ")

    if password != confirm_password:
        print("Error: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    try:
        validate_password_strength(password, username=username)
    except WeakPasswordError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    settings = Settings.from_env()
    init_db(settings.db_path)

    user_repo = SQLiteUserRepository(settings.db_path)
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash(password)

    try:
        user_repo.add(
            username=username,
            password_hash=password_hash,
            role=Role.ADMIN,
            must_change_password=True,
        )
        print(f"Success: Administrator '{username}' created successfully (must_change_password=True).")
        sys.exit(0)
    except UserExistsError:
        print(f"Error: User '{username}' already exists.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
