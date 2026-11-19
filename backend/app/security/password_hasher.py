"""Password hasher protocol and Argon2id implementation."""

from __future__ import annotations

from typing import Protocol
from argon2 import PasswordHasher as _Argon2Hasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError


class PasswordHasher(Protocol):
    """Protocol for hashing and verifying passwords."""

    def hash(self, password: str) -> str:
        """Hash a plain text password."""
        ...

    def verify(self, hash: str, password: str) -> bool:
        """Verify password against hash. Return True on match, False otherwise."""
        ...

    def needs_rehash(self, hash: str) -> bool:
        """Check whether hash parameters need re-hashing."""
        ...


class Argon2PasswordHasher:
    """Argon2id password hasher using default argon2-cffi parameters."""

    def __init__(self) -> None:
        self._hasher = _Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(hash)
        except Exception:
            return True
