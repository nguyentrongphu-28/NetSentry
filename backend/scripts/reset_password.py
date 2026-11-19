#!/usr/bin/env python3
"""CLI script to reset a user's password in NetSentry."""

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
from app.domain.errors import UserNotFoundError, WeakPasswordError
from app.repositories.database import init_db
from app.repositories.sqlite_session_repository import SQLiteSessionRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher
from app.security.password_policy import validate_password_strength


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a user password in NetSentry.")
    parser.add_argument("--username", required=True, help="Username of the user to reset")
    args = parser.parse_args()

    username = args.username.strip().lower()

    settings = Settings.from_env()
    init_db(settings.db_path)

    user_repo = SQLiteUserRepository(settings.db_path)
    session_repo = SQLiteSessionRepository(settings.db_path)
    hasher = Argon2PasswordHasher()

    user_record = user_repo.get_by_username(username)
    if not user_record:
        print(f"Error: User '{username}' not found.", file=sys.stderr)
        sys.exit(2)

    print(f"Resetting password for user '{username}'.")
    password = getpass.getpass("Enter new password: ")
    confirm_password = getpass.getpass("Confirm new password: ")

    if password != confirm_password:
        print("Error: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    try:
        validate_password_strength(password, username=username)
    except WeakPasswordError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    new_hash = hasher.hash(password)
    user_repo.update_password(user_record.id, new_hash, must_change_password=True)
    # Revoke all existing sessions
    session_repo.delete_all_for_user(user_record.id)

    print(f"Success: Password for '{username}' has been reset (must_change_password=True). All sessions revoked.")
    sys.exit(0)


if __name__ == "__main__":
    main()
