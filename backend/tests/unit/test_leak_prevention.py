from __future__ import annotations

import json
import logging
from pathlib import Path
import pytest

from app.domain.entities.finding import FindingStatus
from app.rules.registry import build_default_engine

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "configs"

SENSITIVE_PATTERNS = [
    "FAKE-ENABLE-PW",
    "FAKE-USER-PW",
    "FAKE-COMMUNITY-RW",
    "FAKE-CON-PW",
    "FAKE-VTY-PW",
]


def test_zero_secret_leakage_in_findings_and_logs(caplog: pytest.LogCaptureFixture):
    """Verify that no sensitive credentials ever leak into findings or logs."""
    insecure_cfg_path = FIXTURES_DIR / "ios_insecure.cfg"
    assert insecure_cfg_path.exists()
    content = insecure_cfg_path.read_text(encoding="utf-8")

    engine = build_default_engine()

    with caplog.at_level(logging.DEBUG):
        findings = engine.run(content, device_id="TEST-INSECURE-01")

    assert len(findings) == 8

    # 1. Inspect finding attributes (evidence, rationale, remediation, verification)
    for f in findings:
        for secret in SENSITIVE_PATTERNS:
            # Evidence
            for ev in f.evidence:
                assert secret not in ev, f"Secret '{secret}' leaked into evidence: {ev}"
            # Rationale
            assert secret not in f.rationale, f"Secret '{secret}' leaked into rationale of {f.rule_id}"
            # Remediation
            assert secret not in f.remediation, f"Secret '{secret}' leaked into remediation of {f.rule_id}"
            # Verification
            assert secret not in f.verification, f"Secret '{secret}' leaked into verification of {f.rule_id}"

    # 2. Inspect serialized JSON output
    serialized_all = json.dumps([f.to_dict() for f in findings])
    for secret in SENSITIVE_PATTERNS:
        assert secret not in serialized_all, f"Secret '{secret}' leaked into serialized JSON output!"

    # 3. Inspect caplog records
    log_text = caplog.text
    for secret in SENSITIVE_PATTERNS:
        assert secret not in log_text, f"Secret '{secret}' leaked into captured logs: {log_text}"


def test_fixture_ios_secure_all_eight_pass():
    secure_cfg = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    engine = build_default_engine()
    findings = engine.run(secure_cfg)

    assert len(findings) == 8
    for f in findings:
        assert f.status == FindingStatus.PASS, f"{f.rule_id} expected PASS, got {f.status}: {f.evidence}"


def test_fixture_ios_insecure_all_eight_fail():
    insecure_cfg = (FIXTURES_DIR / "ios_insecure.cfg").read_text(encoding="utf-8")
    engine = build_default_engine()
    findings = engine.run(insecure_cfg)

    assert len(findings) == 8
    for f in findings:
        assert f.status == FindingStatus.FAIL, f"{f.rule_id} expected FAIL, got {f.status}: {f.evidence}"


def test_fixture_ios_minimal_eight_rule_expectations():
    """Verify full 8-rule status expectations for ios_minimal.cfg (User adjustment #4)."""
    minimal_cfg = (FIXTURES_DIR / "ios_minimal.cfg").read_text(encoding="utf-8")
    engine = build_default_engine()
    findings = engine.run(minimal_cfg)

    assert len(findings) == 8
    results_map = {f.rule_id: f.status for f in findings}

    expected_statuses = {
        "NET-001": FindingStatus.UNKNOWN,  # No VTY lines
        "NET-002": FindingStatus.FAIL,     # Missing 'ip ssh version 2'
        "NET-003": FindingStatus.PASS,     # No plaintext passwords
        "NET-004": FindingStatus.FAIL,     # Missing 'service password-encryption'
        "NET-005": FindingStatus.UNKNOWN,  # No VTY lines
        "NET-006": FindingStatus.UNKNOWN,  # No VTY lines
        "NET-007": FindingStatus.PASS,     # No SNMP community strings
        "NET-008": FindingStatus.PASS,     # No unencrypted HTTP server
    }

    assert results_map == expected_statuses


def test_fixture_ios_banner_trap_net001_pass():
    banner_cfg = (FIXTURES_DIR / "ios_banner_trap.cfg").read_text(encoding="utf-8")
    engine = build_default_engine()
    findings = engine.run(banner_cfg)

    net001 = next(f for f in findings if f.rule_id == "NET-001")
    assert net001.status == FindingStatus.PASS
