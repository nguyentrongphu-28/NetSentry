"""Unit tests for password hasher, password policy, and security tokens (Section 9.1)."""

import pytest
from app.domain.errors import WeakPasswordError
from app.security.password_hasher import Argon2PasswordHasher
from app.security.password_policy import validate_password_strength
from app.security.tokens import TokenGenerator, hash_token


class TestArgon2PasswordHasher:
    def test_hash_and_verify_success(self) -> None:
        hasher = Argon2PasswordHasher()
        pwd = "CorrectHorseBatteryStaple2026!"
        h = hasher.hash(pwd)

        assert h.startswith("$argon2id$")
        assert hasher.verify(h, pwd) is True

    def test_hash_differs_for_same_password_due_to_salt(self) -> None:
        hasher = Argon2PasswordHasher()
        pwd = "CorrectHorseBatteryStaple2026!"
        h1 = hasher.hash(pwd)
        h2 = hasher.hash(pwd)

        assert h1 != h2
        assert hasher.verify(h1, pwd) is True
        assert hasher.verify(h2, pwd) is True

    def test_verify_fails_for_wrong_password(self) -> None:
        hasher = Argon2PasswordHasher()
        h = hasher.hash("CorrectPassword123!")
        assert hasher.verify(h, "WrongPassword123!") is False
        assert hasher.verify(h, "correcTPassword123!") is False

    def test_verify_handles_malformed_hash_gracefully(self) -> None:
        hasher = Argon2PasswordHasher()
        assert hasher.verify("not-a-valid-argon2-hash", "password") is False
        assert hasher.verify("", "password") is False

    def test_needs_rehash(self) -> None:
        hasher = Argon2PasswordHasher()
        h = hasher.hash("SecurePasswordTest123!")
        assert hasher.needs_rehash(h) is False
        assert hasher.needs_rehash("invalid-hash") is True


class TestPasswordPolicy:
    def test_valid_passwords_pass(self) -> None:
        validate_password_strength("ValidPassword123!", username="alice")
        validate_password_strength("MySuperSecretNetSentryPhrase2026", username="bob")

    def test_too_short_raises_weak_password(self) -> None:
        with pytest.raises(WeakPasswordError, match="at least 12 characters"):
            validate_password_strength("Short123!", username="alice")

    def test_too_long_raises_weak_password(self) -> None:
        with pytest.raises(WeakPasswordError, match="at most 128 characters"):
            validate_password_strength("A" * 129, username="alice")

    def test_single_repeated_char_raises_weak_password(self) -> None:
        with pytest.raises(WeakPasswordError, match="single repeated character"):
            validate_password_strength("aaaaaaaaaaaaaaaa", username="alice")

    def test_contains_whitespace_raises_weak_password(self) -> None:
        with pytest.raises(WeakPasswordError, match="whitespace"):
            validate_password_strength("Password With Space 123", username="alice")

    def test_common_password_raises_weak_password(self) -> None:
        with pytest.raises(WeakPasswordError, match="too common"):
            validate_password_strength("password1234", username="alice")
        with pytest.raises(WeakPasswordError, match="too common"):
            validate_password_strength("admin12345678", username="alice")

    def test_contains_username_raises_weak_password(self) -> None:
        with pytest.raises(WeakPasswordError, match="contain your username"):
            validate_password_strength("SuperSecretAlice2026!", username="alice")
        with pytest.raises(WeakPasswordError, match="contain your username"):
            validate_password_strength("administrator123", username="admin")


class TestTokens:
    def test_token_generator_entropy(self) -> None:
        t1 = TokenGenerator.generate_token(32)
        t2 = TokenGenerator.generate_token(32)
        assert len(t1) >= 40
        assert t1 != t2

    def test_hash_token_sha256(self) -> None:
        raw = "test_token_sample"
        h = hash_token(raw)
        assert len(h) == 64
        assert h == hash_token(raw)
