"""Password strength validation policy."""

from __future__ import annotations

from app.domain.errors import WeakPasswordError

# Common weak passwords list (~50 entries)
COMMON_PASSWORDS = {
    "password1234",
    "password12345",
    "admin123456",
    "admin12345678",
    "netsentry123",
    "netsentry1234",
    "123456789012",
    "1234567890123",
    "qwertyuiop12",
    "qwertyuiopas",
    "welcome12345",
    "welcome123456",
    "administrator1",
    "iloveyou12345",
    "changeme12345",
    "cisco12345678",
    "ciscocisco12",
    "pass12345678",
    "secret123456",
    "testing12345",
    "default12345",
    "monkey123456",
    "dragon123456",
    "sunshine1234",
    "princess1234",
    "football1234",
    "baseball1234",
    "trustno11234",
    "superman1234",
    "batman123456",
    "jordan123456",
    "harley123456",
    "shadow123456",
    "master123456",
    "security1234",
    "correcthorse",
    "starwars1234",
    "computer1234",
    "access123456",
    "keyboard1234",
    "network12345",
    "ciscoios1234",
    "router123456",
    "switch123456",
    "gateway12345",
    "firewall1234",
    "telecom12345",
    "support12345",
    "service12345",
    "system123456",
}


def validate_password_strength(password: str, username: str | None = None) -> None:
    """Validate password strength according to NetSentry security specifications.

    Rules:
    - Length between 12 and 128 characters.
    - Cannot equal or contain normalized username (case-insensitive, if len(username) >= 3).
    - Cannot be in common weak passwords blacklist.
    - Cannot consist of a single repeated character.
    - Must not contain whitespace.

    Raises WeakPasswordError with descriptive rule messages (never mentions the input password).
    """
    if len(password) < 12:
        raise WeakPasswordError("Password must be at least 12 characters long.")
    if len(password) > 128:
        raise WeakPasswordError("Password must be at most 128 characters long.")

    if len(set(password)) <= 1:
        raise WeakPasswordError("Password cannot consist of a single repeated character.")

    if any(c.isspace() for c in password):
        raise WeakPasswordError("Password cannot contain whitespace characters.")

    norm_password = password.strip().lower()
    if norm_password in COMMON_PASSWORDS:
        raise WeakPasswordError("Password is too common and easily guessable.")

    if username:
        norm_username = username.strip().lower()
        if len(norm_username) >= 3:
            if norm_username == norm_password or norm_username in norm_password:
                raise WeakPasswordError("Password cannot contain your username.")
