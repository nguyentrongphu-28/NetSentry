"""Secure token generation and cryptographic hashing."""

from __future__ import annotations

import hashlib
import secrets


class TokenGenerator:
    """Cryptographically secure token generator."""

    @staticmethod
    def generate_token(nbytes: int = 32) -> str:
        """Generate a URL-safe random string with high entropy."""
        return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """Hash raw session token using SHA-256 for persistent database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
