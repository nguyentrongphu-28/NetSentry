"""Tests for documentation consistency and link integrity (Spec Section 8.1)."""

from pathlib import Path
import re
import pytest

from app.rules.registry import build_default_engine
from app.remediation.templates import get_all_templates
from scripts.check_docs_links import check_markdown_links


def test_docs_links_integrity():
    """Verify that all relative file links in docs/ and README.md point to real existing files."""
    total, broken, errors = check_markdown_links()
    assert broken == 0, f"Detected {broken} broken links in documentation:\n" + "\n".join(errors)
    assert total > 0


def test_rules_catalog_matches_code():
    """Verify that all 8 rules in RuleEngine are documented in docs/rules_catalog.md."""
    catalog_path = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "rules_catalog.md"
    assert catalog_path.is_file()
    catalog_text = catalog_path.read_text(encoding="utf-8")

    engine = build_default_engine()
    engine_rules = {rule.rule_id for rule in engine._rules}

    assert len(engine_rules) == 8
    for rid in engine_rules:
        assert rid in catalog_text, f"Rule {rid} implemented in code but missing in docs/rules_catalog.md"


def test_remediation_templates_documented():
    """Verify that all available remediation templates are documented in architecture docs."""
    templates = get_all_templates()
    template_rule_ids = {t.rule_id for t in templates}

    assert "NET-004" in template_rule_ids
    assert "NET-008" in template_rule_ids

    arch_doc = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "architecture.md"
    content = arch_doc.read_text(encoding="utf-8")
    for rid in template_rule_ids:
        assert rid in content, f"Remediation template {rid} not referenced in docs/architecture.md"


def test_readme_environment_dependencies_consistent():
    """Ensure README mentions exact netmiko and paramiko pins."""
    readme_path = Path(__file__).resolve().parent.parent.parent.parent / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    assert "netmiko==4.8.0" in readme_text
    assert "paramiko==5.1.0" in readme_text
