from __future__ import annotations

import textwrap
import pytest

from app.domain.entities.finding import FindingStatus, Severity
from app.rules.ios_config_parser import IosConfigParser
from app.rules.vty_acl_rule import VtyAccessClassRule


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


@pytest.fixture
def rule() -> VtyAccessClassRule:
    return VtyAccessClassRule()


def test_vty_acl_metadata(rule: VtyAccessClassRule):
    assert rule.rule_id == "NET-006"
    assert rule.title == "Restrict VTY access using Access Control List"
    assert rule.severity == Severity.MEDIUM


def test_vty_acl_pass_numbered_and_named(parser: IosConfigParser, rule: VtyAccessClassRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         access-class 10 in
        line vty 5 15
         access-class ADMIN_VTY in vrf-also
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS
    assert len(findings[0].evidence) == 2


def test_vty_acl_fail_missing(parser: IosConfigParser, rule: VtyAccessClassRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         transport input ssh
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert any("line vty 0 4: missing 'access-class ... in'" in e for e in findings[0].evidence)


def test_vty_acl_fail_out_direction_only(parser: IosConfigParser, rule: VtyAccessClassRule):
    # Only outbound ACL configured, inbound is missing -> FAIL
    raw = textwrap.dedent(
        """\
        line vty 0 4
         access-class 10 out
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL


def test_vty_acl_unknown_no_vty(parser: IosConfigParser, rule: VtyAccessClassRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.UNKNOWN


def test_vty_acl_mixed_blocks_priority_fail(parser: IosConfigParser, rule: VtyAccessClassRule):
    # Block 0 4 has valid inbound ACL (PASS)
    # Block 5 15 missing inbound ACL (FAIL)
    # Expected: FAIL (priority FAIL > UNKNOWN > PASS)
    raw = textwrap.dedent(
        """\
        line vty 0 4
         access-class 10 in
        line vty 5 15
         transport input ssh
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert any("line vty 5 15" in e for e in findings[0].evidence)
