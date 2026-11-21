"""Unit tests for config_blocks and DriftService (Spec 9.1 & 9.2)."""

import time
import pytest
from app.domain.entities.drift import BlockChangeKind
from app.services.config_blocks import split_blocks
from app.services.drift_service import DriftService


def test_config_blocks_splitting():
    config = """
! Last configuration change at 12:00:00
hostname Router1
service password-encryption

interface GigabitEthernet0/1
 description Primary Uplink
 ip address 10.0.0.1 255.255.255.0
 no shutdown

ip access-list extended MGMT
 permit tcp 10.1.0.0 0.0.255.255 any eq 22
 deny ip any any

banner motd ^C
Authorized Access Only!
Disconnect immediately if unauthorized.
^C

line vty 0 4
 transport input ssh
 login local
!
end
"""
    blocks = split_blocks(config)

    assert "(global)" in blocks
    assert "hostname Router1" in blocks["(global)"]
    assert "service password-encryption" in blocks["(global)"]

    assert "interface GigabitEthernet0/1" in blocks
    assert blocks["interface GigabitEthernet0/1"] == [
        "description Primary Uplink",
        "ip address 10.0.0.1 255.255.255.0",
        "no shutdown",
    ]

    assert "ip access-list extended MGMT" in blocks
    assert len(blocks["ip access-list extended MGMT"]) == 2
    assert blocks["ip access-list extended MGMT"][0] == "permit tcp 10.1.0.0 0.0.255.255 any eq 22"

    assert "banner motd" in blocks
    assert any("Authorized Access Only!" in line for line in blocks["banner motd"])

    assert "line vty 0 4" in blocks
    assert blocks["line vty 0 4"] == ["transport input ssh", "login local"]


def test_config_blocks_large_input_not_hang():
    # 1 MB of repetitive blocks
    single_block = "interface GigabitEthernet0/1\n ip address 10.0.0.1 255.255.255.0\n no shutdown\n"
    repeat_count = (1024 * 1024) // len(single_block)
    large_config = single_block * repeat_count

    start_time = time.monotonic()
    blocks = split_blocks(large_config)
    duration = time.monotonic() - start_time

    assert duration < 5.0, f"split_blocks took too long ({duration:.2f}s) for 1MB input"
    assert "interface GigabitEthernet0/1" in blocks


def test_drift_service_identical_in_sync():
    service = DriftService()
    cfg = "hostname R1\nservice password-encryption\n"
    report = service.compare(
        device_id="dev1",
        baseline_id=1,
        run_id=10,
        baseline_text=cfg,
        current_text=cfg,
    )
    assert report.summary.status == "IN_SYNC"
    assert len(report.blocks) == 0


def test_drift_service_acl_order_change_is_drift():
    service = DriftService()
    base = """
ip access-list extended TEST
 permit ip 10.0.0.0 0.255.255.255 any
 deny ip any any
"""
    curr = """
ip access-list extended TEST
 deny ip any any
 permit ip 10.0.0.0 0.255.255.255 any
"""
    report = service.compare(
        device_id="dev1",
        baseline_id=1,
        run_id=10,
        baseline_text=base,
        current_text=curr,
    )
    assert report.summary.status == "DRIFTED"
    assert len(report.blocks) == 1
    blk = report.blocks[0]
    assert blk.key == "ip access-list extended TEST"
    assert blk.kind == BlockChangeKind.CHANGED
    assert blk.security_relevant is True


def test_drift_service_global_order_change_is_not_drift():
    service = DriftService()
    base = "hostname R1\nservice password-encryption\n"
    curr = "service password-encryption\nhostname R1\n"
    report = service.compare(
        device_id="dev1",
        baseline_id=1,
        run_id=10,
        baseline_text=base,
        current_text=curr,
    )
    assert report.summary.status == "IN_SYNC"
    assert len(report.blocks) == 0


def test_drift_service_global_line_change_and_security_flag():
    service = DriftService()
    base = "hostname R1\nip ssh version 2\n"
    curr = "hostname R1\nip ssh version 1\n"
    report = service.compare(
        device_id="dev1",
        baseline_id=1,
        run_id=10,
        baseline_text=base,
        current_text=curr,
    )
    assert report.summary.status == "DRIFTED"
    assert len(report.blocks) == 1
    blk = report.blocks[0]
    assert blk.key == "(global)"
    assert blk.kind == BlockChangeKind.CHANGED
    assert blk.security_relevant is True
    assert "ip ssh version 1" in blk.added_lines
    assert "ip ssh version 2" in blk.removed_lines


def test_drift_service_redacted_secrets_do_not_leak():
    service = DriftService()
    base = "enable secret <REDACTED:aaaaaa>\n"
    curr = "enable secret <REDACTED:bbbbbb>\n"
    report = service.compare(
        device_id="dev1",
        baseline_id=1,
        run_id=10,
        baseline_text=base,
        current_text=curr,
        include_lines=True,
    )
    assert report.summary.status == "DRIFTED"
    blk = report.blocks[0]
    assert "SENTINEL" not in str(blk.added_lines)
    assert "<REDACTED:bbbbbb>" in blk.added_lines[0]
