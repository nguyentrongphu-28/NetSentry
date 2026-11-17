from __future__ import annotations

import textwrap
import pytest

from app.domain.entities.finding import FindingStatus, Severity
from app.rules.ios_config_parser import IosConfigParser
from app.rules.snmp_rule import SnmpCommunityRule


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


@pytest.fixture
def rule() -> SnmpCommunityRule:
    return SnmpCommunityRule()


def test_snmp_rule_metadata(rule: SnmpCommunityRule):
    assert rule.rule_id == "NET-007"
    assert rule.title == "Disallow insecure SNMP community strings"
    assert rule.severity == Severity.MEDIUM


def test_snmp_rule_pass(parser: IosConfigParser, rule: SnmpCommunityRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        ip ssh version 2
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS
    assert findings[0].severity == Severity.MEDIUM


def test_snmp_rule_fail_medium_severity(parser: IosConfigParser, rule: SnmpCommunityRule):
    # Custom non-default RO community string -> FAIL with Severity.MEDIUM
    raw = textwrap.dedent(
        """\
        hostname R1
        snmp-server community MyCustomROString RO 10
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    f = findings[0]
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.MEDIUM
    # Must be redacted in evidence
    assert "MyCustomROString" not in str(f.evidence)
    assert any("snmp-server community <REDACTED> RO 10" in e for e in f.evidence)


def test_snmp_rule_fail_escalate_rw(parser: IosConfigParser, rule: SnmpCommunityRule):
    # RW community string -> escalates to Severity.HIGH
    raw = textwrap.dedent(
        """\
        hostname R1
        snmp-server community secretRWString RW
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    f = findings[0]
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.HIGH
    assert "secretRWString" not in str(f.evidence)


def test_snmp_rule_fail_escalate_public_default(parser: IosConfigParser, rule: SnmpCommunityRule):
    # Default 'public' string -> escalates to Severity.HIGH
    raw = textwrap.dedent(
        """\
        hostname R1
        snmp-server community public RO
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert findings[0].severity == Severity.HIGH


def test_snmp_rule_fail_escalate_private_default(parser: IosConfigParser, rule: SnmpCommunityRule):
    # Default 'private' string -> escalates to Severity.HIGH
    raw = textwrap.dedent(
        """\
        hostname R1
        snmp-server community private RO
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert findings[0].severity == Severity.HIGH
