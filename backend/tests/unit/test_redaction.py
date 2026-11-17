from __future__ import annotations

import pytest

from app.core.redaction import REDACTED, redact_line


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("enable password 0 MyPass1", f"enable password 0 {REDACTED}"),
        ("enable password MyPass1", f"enable password {REDACTED}"),
        ("enable secret 5 $1$abc$xyz", f"enable secret 5 {REDACTED}"),
        (
            "username admin privilege 15 password 0 Pass1",
            f"username admin privilege 15 password 0 {REDACTED}",
        ),
        (
            "username admin secret 9 $9$xxxx",
            f"username admin secret 9 {REDACTED}",
        ),
        (" password 7 0822455D0A16", f" password 7 {REDACTED}"),
        (
            "snmp-server community public RO",
            f"snmp-server community {REDACTED} RO",
        ),
        (
            "snmp-server community s3cr3t RW 10",
            f"snmp-server community {REDACTED} RW 10",
        ),
        ("tacacs-server key 7 TacPass", f"tacacs-server key 7 {REDACTED}"),
        ("radius-server key 0 RadiusPass", f"radius-server key 0 {REDACTED}"),
        (
            "snmp-server host 1.2.3.4 version 2c secretstr",
            f"snmp-server host 1.2.3.4 version 2c {REDACTED}",
        ),
    ],
)
def test_redact_line_spec_table(original: str, expected: str):
    redacted = redact_line(original)
    assert redacted == expected
    # Idempotency check: running redact_line again should yield exact same result
    assert redact_line(redacted) == expected


@pytest.mark.parametrize(
    "benign_line",
    [
        "hostname Core-Router",
        "ip ssh version 2",
        "transport input ssh",
        "exec-timeout 5 0",
        "access-class 10 in",
        "service password-encryption",
        "no ip http server",
        "interface GigabitEthernet0/0",
        " ip address 192.168.1.1 255.255.255.0",
        "",
        "   ",
        "!",
    ],
)
def test_redact_line_benign_lines_unchanged(benign_line: str):
    assert redact_line(benign_line) == benign_line


def test_redact_line_case_insensitivity():
    line = "ENABLE PASSWORD 0 TopSecret"
    expected = f"ENABLE PASSWORD 0 {REDACTED}"
    assert redact_line(line) == expected
    assert redact_line(expected) == expected
