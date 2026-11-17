from __future__ import annotations

import textwrap
import pytest

from app.domain.entities.finding import FindingStatus, Severity
from app.rules.ios_config_parser import IosConfigParser
from app.rules.vty_timeout_rule import VtyExecTimeoutRule


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


@pytest.fixture
def rule() -> VtyExecTimeoutRule:
    return VtyExecTimeoutRule()


def test_vty_timeout_metadata(rule: VtyExecTimeoutRule):
    assert rule.rule_id == "NET-005"
    assert rule.title == "Enforce VTY executive session timeout"
    assert rule.severity == Severity.MEDIUM


def test_vty_timeout_pass(parser: IosConfigParser, rule: VtyExecTimeoutRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         exec-timeout 5 0
        line vty 5 15
         exec-timeout 10 0
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS
    assert len(findings[0].evidence) == 2


def test_vty_timeout_fail_disabled(parser: IosConfigParser, rule: VtyExecTimeoutRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         exec-timeout 0 0
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert any("timeout disabled" in e for e in findings[0].evidence)


def test_vty_timeout_fail_excessive(parser: IosConfigParser, rule: VtyExecTimeoutRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         exec-timeout 15 0
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert any("900s > 600s" in e for e in findings[0].evidence)


def test_vty_timeout_unknown_no_vty(parser: IosConfigParser, rule: VtyExecTimeoutRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.UNKNOWN


def test_vty_timeout_unknown_missing_timeout(parser: IosConfigParser, rule: VtyExecTimeoutRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         transport input ssh
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.UNKNOWN


def test_vty_timeout_mixed_blocks_priority_fail(parser: IosConfigParser, rule: VtyExecTimeoutRule):
    # Block 0 4 lacks exec-timeout (UNKNOWN candidate)
    # Block 5 15 has exec-timeout 0 0 (FAIL violation)
    # Expected: FAIL (priority FAIL > UNKNOWN > PASS)
    raw = textwrap.dedent(
        """\
        line vty 0 4
         transport input ssh
        line vty 5 15
         exec-timeout 0 0
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert any("timeout disabled" in e for e in findings[0].evidence)
