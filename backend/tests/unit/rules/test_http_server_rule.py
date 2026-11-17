from __future__ import annotations

import textwrap
import pytest

from app.domain.entities.finding import FindingStatus, Severity
from app.rules.http_server_rule import HttpServerRule
from app.rules.ios_config_parser import IosConfigParser


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


@pytest.fixture
def rule() -> HttpServerRule:
    return HttpServerRule()


def test_http_server_metadata(rule: HttpServerRule):
    assert rule.rule_id == "NET-008"
    assert rule.title == "Disable unencrypted HTTP server"
    assert rule.severity == Severity.MEDIUM


def test_http_server_pass_explicit_no(parser: IosConfigParser, rule: HttpServerRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        no ip http server
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS
    assert "no ip http server" in findings[0].evidence


def test_http_server_pass_absent(parser: IosConfigParser, rule: HttpServerRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS


def test_http_server_pass_secure_server(parser: IosConfigParser, rule: HttpServerRule):
    # 'ip http secure-server' (HTTPS) is allowed and not a violation
    raw = textwrap.dedent(
        """\
        hostname R1
        ip http secure-server
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.PASS


def test_http_server_fail_unencrypted(parser: IosConfigParser, rule: HttpServerRule):
    raw = textwrap.dedent(
        """\
        hostname R1
        ip http server
        """
    )
    findings = rule.check(parser.parse(raw))
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.FAIL
    assert "ip http server" in findings[0].evidence
