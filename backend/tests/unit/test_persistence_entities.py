"""Unit tests for persistence domain entities and persistence domain errors."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import pytest

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.audit_run import AuditRunDetail, AuditRunSummary
from app.domain.entities.device import Device, DeviceTarget
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.errors import (
    AuditAlreadyRunningError,
    AuditNotFoundError,
    CredentialsRequiredError,
    DeviceNotFoundError,
    DuplicateDeviceError,
    InvalidDeviceError,
    NetSentryError,
)


class TestDeviceEntity:
    def test_device_creation_and_attributes(self):
        now = datetime.now(timezone.utc)
        dev = Device(
            device_id="R1",
            name="Core Router 1",
            host="192.168.1.1",
            port=22,
            platform="cisco_ios",
            created_at=now,
            updated_at=now,
        )
        assert dev.device_id == "R1"
        assert dev.name == "Core Router 1"
        assert dev.host == "192.168.1.1"
        assert dev.port == 22
        assert dev.platform == "cisco_ios"
        assert dev.created_at == now
        assert dev.updated_at == now

    def test_device_to_target(self):
        now = datetime.now(timezone.utc)
        dev = Device(
            device_id="R1",
            name="Router",
            host="10.1.1.1",
            port=2222,
            platform="cisco_ios",
            created_at=now,
            updated_at=now,
        )
        target = dev.to_target()
        assert isinstance(target, DeviceTarget)
        assert target.device_id == "R1"
        assert target.host == "10.1.1.1"
        assert target.port == 2222
        assert target.platform == "cisco_ios"

    def test_device_is_frozen(self):
        now = datetime.now(timezone.utc)
        dev = Device(
            device_id="R1",
            name="Router",
            host="10.1.1.1",
            port=22,
            platform="cisco_ios",
            created_at=now,
            updated_at=now,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            dev.port = 8022  # type: ignore[misc]

    def test_no_credential_or_config_fields(self):
        field_names = [f.name.lower() for f in dataclasses.fields(Device)]
        for forbidden in ("password", "secret", "cred", "config"):
            assert not any(forbidden in f for f in field_names)


class TestAuditRunEntities:
    def test_audit_run_summary_and_detail(self):
        now = datetime.now(timezone.utc)
        summary = AuditRunSummary(
            id=1,
            device_id="R1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=now,
            finished_at=now,
            hostname="R1-Host",
            error_code=None,
            error_message=None,
            pass_count=1,
            fail_count=0,
            unknown_count=0,
        )
        assert summary.id == 1
        assert summary.device_id == "R1"
        assert summary.status == AuditStatus.COMPLETED

        finding = Finding(
            rule_id="SEC-01",
            title="Enable secret check",
            severity=Severity.HIGH,
            status=FindingStatus.PASS,
            evidence=("evidence 1",),
            rationale="Rationale",
            remediation="Remediation",
            verification="Verification",
        )
        detail = AuditRunDetail(summary=summary, findings=(finding,))
        assert detail.summary == summary
        assert len(detail.findings) == 1
        assert detail.findings[0] == finding

    def test_entities_are_frozen(self):
        now = datetime.now(timezone.utc)
        summary = AuditRunSummary(
            id=1,
            device_id="R1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=now,
            finished_at=now,
            hostname=None,
            error_code=None,
            error_message=None,
            pass_count=0,
            fail_count=0,
            unknown_count=0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            summary.status = AuditStatus.FAILED  # type: ignore[misc]

    def test_no_credential_or_config_fields(self):
        for cls in (AuditRunSummary, AuditRunDetail):
            field_names = [f.name.lower() for f in dataclasses.fields(cls)]
            for forbidden in ("password", "secret", "cred", "config"):
                assert not any(forbidden in f for f in field_names)


class TestDomainErrors:
    @pytest.mark.parametrize(
        ("error_cls", "expected_code"),
        [
            (DeviceNotFoundError, "DEVICE_NOT_FOUND"),
            (DuplicateDeviceError, "DEVICE_EXISTS"),
            (InvalidDeviceError, "INVALID_DEVICE"),
            (AuditNotFoundError, "AUDIT_NOT_FOUND"),
            (AuditAlreadyRunningError, "AUDIT_ALREADY_RUNNING"),
            (CredentialsRequiredError, "CREDENTIALS_REQUIRED"),
        ],
    )
    def test_error_classes_and_codes(self, error_cls: type[NetSentryError], expected_code: str):
        err = error_cls("Test error message")
        assert issubclass(error_cls, NetSentryError)
        assert err.code == expected_code
        assert str(err) == "Test error message"
