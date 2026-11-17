from __future__ import annotations

import textwrap
import pytest

from app.domain.entities.finding import FindingStatus, Severity
from app.rules.ios_config_parser import IosConfigParser
from app.rules.ssh_rule import SshVersionRule


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


@pytest.fixture
def rule() -> SshVersionRule:
    return SshVersionRule()


def test_ssh_rule_metadata(rule: SshVersionRule):
    assert rule.rule_id == "NET-002"
    assert rule.title == "Enforce SSH version 2"
    assert rule.severity == Severity.MEDIUM
    assert rule.platforms == ("cisco_ios",)


def test_ssh_rule_pass(parser: IosConfigParser, rule: SshVersionRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        ip ssh version 2
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS
    assert findings[0].rule_id == "NET-002"
    assert "ip ssh version 2" in findings[0].evidence


def test_ssh_rule_fail_v1(parser: IosConfigParser, rule: SshVersionRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        ip ssh version 1
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert findings[0].severity == Severity.MEDIUM
    assert "ip ssh version 1" in findings[0].evidence


def test_ssh_rule_fail_missing_ssh_v2(parser: IosConfigParser, rule: SshVersionRule):
    # Requirement: missing 'ip ssh version 2' MUST be FAIL, NOT UNKNOWN
    raw = textwrap.dedent(
        """\
        hostname R1
        interface GigabitEthernet0/0
         ip address 10.0.0.1 255.255.255.0
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert findings[0].status != FindingStatus.UNKNOWN
