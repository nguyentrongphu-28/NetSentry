from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import pytest

from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.entities.parsed_config import ConfigBlock, ParsedConfig
from app.domain.interfaces.audit_rule import AuditRule


def test_finding_creation_and_to_dict():
    dt = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
    finding = Finding(
        rule_id="NET-001",
        title="Disallow Telnet on VTY lines",
        severity=Severity.HIGH,
        status=FindingStatus.FAIL,
        evidence=("line vty 0 4: transport input telnet",),
        rationale="Telnet sends credentials in cleartext.",
        remediation="Configure transport input ssh.",
        verification="Check show running-config.",
        device_id="R1",
        checked_at=dt,
    )

    data = finding.to_dict()
    assert data["rule_id"] == "NET-001"
    assert data["title"] == "Disallow Telnet on VTY lines"
    assert data["severity"] == "HIGH"
    assert data["status"] == "FAIL"
    assert data["evidence"] == ["line vty 0 4: transport input telnet"]
    assert data["device_id"] == "R1"
    assert data["checked_at"] == "2026-11-16T12:00:00+00:00"


def test_finding_frozen_immutability():
    finding = Finding(
        rule_id="NET-001",
        title="Test",
        severity=Severity.LOW,
        status=FindingStatus.PASS,
        evidence=(),
        rationale="None",
        remediation="None",
        verification="None",
    )

    with pytest.raises(FrozenInstanceError):
        finding.title = "Modified"  # type: ignore[misc]


def test_config_block_helpers():
    block = ConfigBlock(
        header="line vty 0 4",
        children=(
            "Transport Input SSH",
            "Exec-Timeout 5 0",
            "access-class 10 in",
        ),
    )

    # child_starting_with (case-insensitive, returns original casing)
    matches = block.child_starting_with("transport input")
    assert matches == ["Transport Input SSH"]

    empty_matches = block.child_starting_with("logging")
    assert empty_matches == []

    # has_child
    assert block.has_child("exec-timeout") is True
    assert block.has_child("EXEC-TIMEOUT") is True
    assert block.has_child("password") is False


def test_parsed_config_helpers():
    b1 = ConfigBlock(header="line vty 0 4", children=("transport input ssh",))
    b2 = ConfigBlock(header="interface GigabitEthernet0/0", children=("ip address 10.0.0.1 255.255.255.0",))
    config = ParsedConfig(
        global_lines=(
            "hostname Core-Router",
            "ip ssh version 2",
            "service password-encryption",
        ),
        blocks=(b1, b2),
    )

    # global_starting_with
    assert config.global_starting_with("ip ssh") == ["ip ssh version 2"]
    assert config.global_starting_with("IP SSH") == ["ip ssh version 2"]
    assert config.global_starting_with("snmp-server") == []

    # has_global
    assert config.has_global("hostname Core-Router") is True
    assert config.has_global("HOSTNAME CORE-ROUTER") is True
    assert config.has_global("hostname Edge-Router") is False

    # blocks_starting_with
    vty_blocks = config.blocks_starting_with("line vty")
    assert len(vty_blocks) == 1
    assert vty_blocks[0].header == "line vty 0 4"

    int_blocks = config.blocks_starting_with("INTERFACE")
    assert len(int_blocks) == 1
    assert int_blocks[0].header == "interface GigabitEthernet0/0"


def test_audit_rule_applies_to():
    class DummyRule(AuditRule):
        rule_id = "NET-TEST"
        title = "Test Rule"
        severity = Severity.LOW
        platforms = ("cisco_ios", "cisco_xe")

        def check(self, config: ParsedConfig) -> list[Finding]:
            return []

    rule = DummyRule()
    assert rule.applies_to("cisco_ios") is True
    assert rule.applies_to("cisco_xe") is True
    assert rule.applies_to("juniper_junos") is False
