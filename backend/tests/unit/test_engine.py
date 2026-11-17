from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.domain.interfaces.audit_rule import AuditRule
from app.rules.base_rule import BaseRule
from app.rules.engine import RuleEngine
from app.rules.ios_config_parser import IosConfigParser


class DummyRuleA(BaseRule):
    rule_id = "NET-001"
    title = "Rule A"
    severity = Severity.LOW
    platforms = ("cisco_ios",)
    description = "Test A"
    remediation_text = "Fix A"
    verification_text = "Verify A"

    def check(self, config: ParsedConfig) -> list[Finding]:
        return [self._pass(note="A passed")]


class DummyRuleB(BaseRule):
    rule_id = "NET-002"
    title = "Rule B"
    severity = Severity.HIGH
    platforms = ("cisco_ios",)
    description = "Test B"
    remediation_text = "Fix B"
    verification_text = "Verify B"

    def check(self, config: ParsedConfig) -> list[Finding]:
        return [self._fail(evidence=("bad line",), rationale="B failed")]


class ExplodingRule(BaseRule):
    rule_id = "NET-099"
    title = "Exploding Rule"
    severity = Severity.CRITICAL
    platforms = ("cisco_ios",)
    description = "Explodes"
    remediation_text = "Fix explosion"
    verification_text = "Verify explosion"

    def check(self, config: ParsedConfig) -> list[Finding]:
        raise RuntimeError("Catastrophic rule bug")


def test_engine_duplicate_rule_id_raises_value_error():
    r1 = DummyRuleA()
    r2 = DummyRuleA()  # same rule_id "NET-001"
    with pytest.raises(ValueError, match="Duplicate rule_id"):
        RuleEngine(rules=[r1, r2], parser=IosConfigParser())


def test_engine_clock_and_device_id_injection():
    fixed_time = datetime(2026, 11, 16, 15, 30, 0, tzinfo=timezone.utc)
    engine = RuleEngine(
        rules=[DummyRuleA()],
        parser=IosConfigParser(),
        clock=lambda: fixed_time,
    )

    findings = engine.run("hostname R1", device_id="ROUTER-HQ-01")
    assert len(findings) == 1
    assert findings[0].device_id == "ROUTER-HQ-01"
    assert findings[0].checked_at == fixed_time


def test_engine_error_isolation():
    # An exception in one rule must be caught and isolated; other rules must still run
    engine = RuleEngine(
        rules=[DummyRuleA(), ExplodingRule(), DummyRuleB()],
        parser=IosConfigParser(),
    )

    findings = engine.run("hostname R1")
    assert len(findings) == 3

    # NET-001 succeeded
    assert findings[0].rule_id == "NET-001"
    assert findings[0].status == FindingStatus.PASS

    # NET-002 succeeded
    assert findings[1].rule_id == "NET-002"
    assert findings[1].status == FindingStatus.FAIL

    # NET-099 caught runtime exception
    assert findings[2].rule_id == "NET-099"
    assert findings[2].status == FindingStatus.UNKNOWN
    assert "rule execution error: RuntimeError" in findings[2].evidence[0]


def test_engine_only_and_skip_rule_ids():
    engine = RuleEngine(
        rules=[DummyRuleA(), DummyRuleB()],
        parser=IosConfigParser(),
    )

    # only_rule_ids
    f_only = engine.run("hostname R1", only_rule_ids=["NET-002"])
    assert len(f_only) == 1
    assert f_only[0].rule_id == "NET-002"

    # skip_rule_ids
    f_skip = engine.run("hostname R1", skip_rule_ids=["NET-002"])
    assert len(f_skip) == 1
    assert f_skip[0].rule_id == "NET-001"


def test_engine_platform_mismatch_skips_rules():
    # Rules targeting cisco_ios should be skipped when platform is juniper_junos
    engine = RuleEngine(
        rules=[DummyRuleA(), DummyRuleB()],
        parser=IosConfigParser(),
    )

    findings = engine.run("hostname R1", platform="juniper_junos")
    assert findings == []


def test_engine_sorts_by_rule_id_ascending():
    # Provide in reverse order
    engine = RuleEngine(
        rules=[DummyRuleB(), DummyRuleA()],
        parser=IosConfigParser(),
    )

    findings = engine.run("hostname R1")
    assert [f.rule_id for f in findings] == ["NET-001", "NET-002"]


def test_engine_determinism():
    fixed_time = datetime(2026, 11, 16, 10, 0, 0, tzinfo=timezone.utc)
    engine = RuleEngine(
        rules=[DummyRuleA(), DummyRuleB()],
        parser=IosConfigParser(),
        clock=lambda: fixed_time,
    )

    cfg = "hostname R1\nline vty 0 4\n transport input ssh"
    run1 = engine.run(cfg, device_id="DEV-01")
    run2 = engine.run(cfg, device_id="DEV-01")

    assert run1 == run2
    assert [f.to_dict() for f in run1] == [f.to_dict() for f in run2]
