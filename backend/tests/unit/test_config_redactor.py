from __future__ import annotations

from pathlib import Path
import time
import pytest

from app.security.config_redactor import ConfigRedactor


@pytest.fixture
def secret_config() -> str:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "config_with_secrets.cfg"
    return fixture_path.read_text(encoding="utf-8")


def test_redactor_removes_all_sentinels(secret_config: str):
    redactor = ConfigRedactor(hmac_key=b"test-secret-key-1")
    redacted = redactor.redact(secret_config)

    # 1. No sentinel string must remain
    assert "SENTINEL_" not in redacted
    assert "<REDACTED:" in redacted

    # 2. Line structure and line count preserved
    assert len(secret_config.splitlines()) == len(redacted.splitlines())

    # 3. Idempotent: redact(redact(x)) == redact(x)
    assert redactor.redact(redacted) == redacted


def test_redactor_fingerprints():
    redactor_a = ConfigRedactor(hmac_key=b"key-alpha")
    redactor_b = ConfigRedactor(hmac_key=b"key-beta")

    secret_1 = "MyPassword123"
    secret_2 = "DifferentPassword456"

    line_1 = f"enable password 0 {secret_1}"
    line_2 = f"enable password 0 {secret_2}"

    res_a_1 = redactor_a.redact_line(line_1)
    res_a_2 = redactor_a.redact_line(line_2)
    res_b_1 = redactor_b.redact_line(line_1)

    # Same secret + same key -> same fingerprint
    assert res_a_1 == redactor_a.redact_line(line_1)

    # Different secret + same key -> different fingerprint
    assert res_a_1 != res_a_2

    # Same secret + different key -> different fingerprint
    assert res_a_1 != res_b_1


def test_redactor_fallback_keywords():
    redactor = ConfigRedactor()

    # Lines with keywords not matching specific IOS commands
    lines = [
        "app-service custom-credential SENTINEL_APP_CRED",
        "api-token bearer SENTINEL_TOKEN_VAL",
        "database auth-secret SENTINEL_DB_SECRET",
        "custom-module secure-key 0 SENTINEL_CUSTOM_KEY",
    ]

    for line in lines:
        redacted = redactor.redact_line(line)
        assert "SENTINEL_" not in redacted
        assert "<REDACTED:" in redacted


def test_redactor_no_catastrophic_backtracking_1mb():
    redactor = ConfigRedactor()
    # 1 MB of repetitive strings that could trigger polynomial/exponential backtracking
    pattern = "username admin privilege 15 " * 10000 + " password 0 Secret123\n"
    large_input = pattern * 5
    assert len(large_input) > 1_000_000

    start_time = time.perf_counter()
    result = redactor.redact(large_input)
    duration = time.perf_counter() - start_time

    assert "Secret123" not in result
    assert duration < 2.0, f"Redaction took too long ({duration:.2f}s) - possible regex backtracking"
