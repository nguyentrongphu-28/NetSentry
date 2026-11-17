from __future__ import annotations

import textwrap
import pytest

from app.domain.entities.finding import FindingStatus, Severity
from app.rules.ios_config_parser import IosConfigParser
from app.rules.password_rule import (
    PasswordEncryptionServiceRule,
    PlainTextCredentialRule,
)


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


# --- NET-003: PlainTextCredentialRule ---


def test_plain_text_credential_metadata():
    rule = PlainTextCredentialRule()
    assert rule.rule_id == "NET-003"
    assert rule.title == "Disallow plaintext or weakly encrypted passwords"
    assert rule.severity == Severity.HIGH


def test_plain_text_credential_pass(parser: IosConfigParser):
    rule = PlainTextCredentialRule()
    raw = textwrap.dedent(
        """\
        hostname R1
        enable secret 9 $9$someHashedSecretValue
        username admin secret 9 $9$adminHashedSecret
        line vty 0 4
         transport input ssh
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS


def test_plain_text_credential_fail_enable_password(parser: IosConfigParser):
    rule = PlainTextCredentialRule()
    raw = textwrap.dedent(
        """\
        hostname R1
        enable password 0 ClearPass123
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    f = findings[0]
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.HIGH
    # Evidence must be redacted
    assert "ClearPass123" not in str(f.evidence)
    assert any("enable password 0 <REDACTED>" in e for e in f.evidence)


def test_plain_text_credential_fail_username_password(parser: IosConfigParser):
    rule = PlainTextCredentialRule()
    raw = textwrap.dedent(
        """\
        hostname R1
        username admin privilege 15 password 0 SecretAdmin123
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    f = findings[0]
    assert f.status == FindingStatus.FAIL
    assert "SecretAdmin123" not in str(f.evidence)
    assert any("<REDACTED>" in e for e in f.evidence)


def test_plain_text_credential_fail_line_password(parser: IosConfigParser):
    rule = PlainTextCredentialRule()
    raw = textwrap.dedent(
        """\
        hostname R1
        line con 0
         password 7 0822455D0A16
        line vty 0 4
         password 0 VtyPassClear
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    f = findings[0]
    assert f.status == FindingStatus.FAIL
    assert "0822455D0A16" not in str(f.evidence)
    assert "VtyPassClear" not in str(f.evidence)
    assert len(f.evidence) == 2


# --- NET-004: PasswordEncryptionServiceRule ---


def test_password_encryption_service_metadata():
    rule = PasswordEncryptionServiceRule()
    assert rule.rule_id == "NET-004"
    assert rule.title == "Enable Cisco password encryption service"
    assert rule.severity == Severity.LOW


def test_password_encryption_service_pass(parser: IosConfigParser):
    rule = PasswordEncryptionServiceRule()
    raw = textwrap.dedent(
        """\
        hostname R1
        service password-encryption
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS
    assert "service password-encryption" in findings[0].evidence


def test_password_encryption_service_fail_missing(parser: IosConfigParser):
    rule = PasswordEncryptionServiceRule()
    raw = textwrap.dedent(
        """\
        hostname R1
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL


def test_password_encryption_service_fail_explicit_no(parser: IosConfigParser):
    rule = PasswordEncryptionServiceRule()
    raw = textwrap.dedent(
        """\
        hostname R1
        no service password-encryption
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert "no service password-encryption" in findings[0].evidence
