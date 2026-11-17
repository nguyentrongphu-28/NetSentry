from __future__ import annotations

from pathlib import Path
import textwrap
import pytest

from app.domain.entities.finding import FindingStatus, Severity
from app.rules.ios_config_parser import IosConfigParser
from app.rules.telnet_rule import TelnetRule

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "configs"


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


@pytest.fixture
def rule() -> TelnetRule:
    return TelnetRule()


def test_telnet_rule_metadata(rule: TelnetRule):
    assert rule.rule_id == "NET-001"
    assert rule.title == "Disallow Telnet on VTY lines"
    assert rule.severity == Severity.HIGH
    assert rule.platforms == ("cisco_ios",)
    assert rule.remediation_text != ""
    assert rule.verification_text != ""


def test_telnet_rule_pass(parser: IosConfigParser, rule: TelnetRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         transport input ssh
        line vty 5 15
         transport input ssh
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    f = findings[0]
    assert f.status == FindingStatus.PASS
    assert f.rule_id == "NET-001"
    assert len(f.evidence) == 2


def test_telnet_rule_pass_transport_none(parser: IosConfigParser, rule: TelnetRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         transport input none
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS


def test_telnet_rule_fail_telnet(parser: IosConfigParser, rule: TelnetRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         transport input telnet ssh
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    f = findings[0]
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.HIGH
    assert any("line vty 0 4: transport input telnet ssh" in e for e in f.evidence)


def test_telnet_rule_fail_all(parser: IosConfigParser, rule: TelnetRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         transport input all
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL


def test_telnet_rule_unknown_no_vty(parser: IosConfigParser, rule: TelnetRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        interface GigabitEthernet0/0
         ip address 10.0.0.1 255.255.255.0
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.UNKNOWN


def test_telnet_rule_unknown_missing_transport_input(parser: IosConfigParser, rule: TelnetRule):
    raw = textwrap.dedent(
        """\
        line vty 0 4
         exec-timeout 5 0
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.UNKNOWN


def test_telnet_rule_mixed_vty_blocks_priority_fail(parser: IosConfigParser, rule: TelnetRule):
    # Block 1 missing transport input (UNKNOWN candidate)
    # Block 2 permits telnet (FAIL)
    # Expected: FAIL (priority FAIL > UNKNOWN > PASS)
    raw = textwrap.dedent(
        """\
        line vty 0 4
         exec-timeout 5 0
        line vty 5 15
         transport input telnet ssh
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert any("line vty 5 15: transport input telnet ssh" in e for e in findings[0].evidence)


def test_telnet_rule_fixtures(parser: IosConfigParser, rule: TelnetRule):
    # ios_secure.cfg -> PASS
    secure_cfg = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    assert rule.check(parser.parse(secure_cfg))[0].status == FindingStatus.PASS

    # ios_insecure.cfg -> FAIL
    insecure_cfg = (FIXTURES_DIR / "ios_insecure.cfg").read_text(encoding="utf-8")
    assert rule.check(parser.parse(insecure_cfg))[0].status == FindingStatus.FAIL

    # ios_minimal.cfg -> UNKNOWN (no VTY)
    minimal_cfg = (FIXTURES_DIR / "ios_minimal.cfg").read_text(encoding="utf-8")
    assert rule.check(parser.parse(minimal_cfg))[0].status == FindingStatus.UNKNOWN

    # ios_banner_trap.cfg -> PASS (banner trap ignored)
    banner_cfg = (FIXTURES_DIR / "ios_banner_trap.cfg").read_text(encoding="utf-8")
    assert rule.check(parser.parse(banner_cfg))[0].status == FindingStatus.PASS
