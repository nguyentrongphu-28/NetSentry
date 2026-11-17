"""Unit tests for device domain entities and audit result."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import pytest

from app.domain.entities.audit_result import AuditResult, AuditStatus
from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.entities.finding import Finding, FindingStatus, Severity


class TestDeviceTarget:
    def test_valid_device_target(self):
        target = DeviceTarget(device_id="R1", host="192.168.1.1", platform="cisco_ios", port=22)
        assert target.device_id == "R1"
        assert target.host == "192.168.1.1"
        assert target.platform == "cisco_ios"
        assert target.port == 22

    def test_default_values(self):
        target = DeviceTarget(device_id="R1", host="10.0.0.1")
        assert target.platform == "cisco_ios"
        assert target.port == 22

    @pytest.mark.parametrize("empty_id", ["", "   "])
    def test_empty_device_id_raises_value_error(self, empty_id: str):
        with pytest.raises(ValueError, match="device_id"):
            DeviceTarget(device_id=empty_id, host="10.0.0.1")

    @pytest.mark.parametrize("empty_host", ["", "   "])
    def test_empty_host_raises_value_error(self, empty_host: str):
        with pytest.raises(ValueError, match="host"):
            DeviceTarget(device_id="R1", host=empty_host)

    @pytest.mark.parametrize("invalid_port", [0, -1, 65536, 100000])
    def test_invalid_port_raises_value_error(self, invalid_port: int):
        with pytest.raises(ValueError, match="port"):
            DeviceTarget(device_id="R1", host="10.0.0.1", port=invalid_port)


class TestCredentials:
    def test_valid_credentials(self):
        creds = Credentials(username="admin", password="SecretPassword123!", enable_secret="EnablePass!")
        assert creds.username == "admin"
        assert creds.password == "SecretPassword123!"
        assert creds.enable_secret == "EnablePass!"

    @pytest.mark.parametrize("empty_user", ["", "   "])
    def test_empty_username_raises_value_error(self, empty_user: str):
        with pytest.raises(ValueError, match="username"):
            Credentials(username=empty_user, password="secret")

    def test_credentials_repr_and_str_do_not_leak_secrets(self):
        secret_pw = "VERY_CONFIDENTIAL_SSH_PW"
        secret_enable = "VERY_CONFIDENTIAL_ENABLE_PW"
        creds = Credentials(username="cisco", password=secret_pw, enable_secret=secret_enable)

        repr_str = repr(creds)
        str_str = str(creds)

        assert secret_pw not in repr_str
        assert secret_enable not in repr_str
        assert secret_pw not in str_str
        assert secret_enable not in str_str
        assert "cisco" in repr_str


class TestAuditResult:
    def test_audit_result_counts_and_to_dict(self):
        now = datetime(2026, 11, 17, 8, 0, 0, tzinfo=timezone.utc)
        f_pass = Finding(
            rule_id="RULE-1",
            title="Rule 1",
            severity=Severity.HIGH,
            status=FindingStatus.PASS,
            evidence=("ev1",),
            rationale="rat1",
            remediation="rem1",
            verification="ver1",
        )
        f_fail = Finding(
            rule_id="RULE-2",
            title="Rule 2",
            severity=Severity.CRITICAL,
            status=FindingStatus.FAIL,
            evidence=("ev2",),
            rationale="rat2",
            remediation="rem2",
            verification="ver2",
        )
        f_unk = Finding(
            rule_id="RULE-3",
            title="Rule 3",
            severity=Severity.LOW,
            status=FindingStatus.UNKNOWN,
            evidence=(),
            rationale="rat3",
            remediation="rem3",
            verification="ver3",
        )

        result = AuditResult(
            device_id="R1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=now,
            finished_at=now,
            findings=(f_pass, f_fail, f_unk),
            hostname="Cisco-R1",
        )

        assert result.pass_count == 1
        assert result.fail_count == 1
        assert result.unknown_count == 1

        d = result.to_dict()
        assert d["device_id"] == "R1"
        assert d["platform"] == "cisco_ios"
        assert d["status"] == "COMPLETED"
        assert d["started_at"] == now.isoformat()
        assert d["finished_at"] == now.isoformat()
        assert d["hostname"] == "Cisco-R1"
        assert d["pass_count"] == 1
        assert d["fail_count"] == 1
        assert d["unknown_count"] == 1
        assert len(d["findings"]) == 3
        assert d["findings"][0]["rule_id"] == "RULE-1"
        assert d["findings"][0]["status"] == "PASS"

    def test_audit_result_does_not_contain_config_fields(self):
        now = datetime.now(timezone.utc)
        result = AuditResult(
            device_id="R1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=now,
            finished_at=now,
        )

        assert not hasattr(result, "config_text")
        field_names = [f.name for f in dataclasses.fields(result)]
        for name in field_names:
            assert "config" not in name.lower(), f"AuditResult should not have field with config: {name}"

        d = result.to_dict()
        for key in d.keys():
            assert "config" not in key.lower(), f"AuditResult dict should not have key with config: {key}"
