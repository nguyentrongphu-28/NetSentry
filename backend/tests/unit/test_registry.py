from __future__ import annotations

from app.domain.entities.finding import Severity
from app.rules.engine import RuleEngine
from app.rules.registry import build_default_engine, get_default_rules


def test_registry_default_rules():
    rules = get_default_rules()
    assert len(rules) == 8

    expected_ids = [
        "NET-001",
        "NET-002",
        "NET-003",
        "NET-004",
        "NET-005",
        "NET-006",
        "NET-007",
        "NET-008",
    ]
    actual_ids = [r.rule_id for r in rules]
    assert actual_ids == expected_ids

    # Rule IDs must be unique
    assert len(set(actual_ids)) == len(actual_ids)

    # Validate metadata of every rule
    for r in rules:
        assert isinstance(r.rule_id, str) and r.rule_id != ""
        assert isinstance(r.title, str) and r.title != ""
        assert isinstance(r.severity, Severity)
        assert isinstance(r.platforms, tuple) and len(r.platforms) > 0
        assert "cisco_ios" in r.platforms
        assert hasattr(r, "description") and r.description != ""
        assert hasattr(r, "remediation_text") and r.remediation_text != ""
        assert hasattr(r, "verification_text") and r.verification_text != ""


def test_registry_build_default_engine():
    engine = build_default_engine()
    assert isinstance(engine, RuleEngine)
    assert len(engine._rules) == 8
