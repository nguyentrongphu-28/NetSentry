"""Live integration test for Cisco IOS connector and AuditService against real hardware."""

from __future__ import annotations

import os
import pytest

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.device import Credentials, DeviceTarget
from app.factories.connector_factory import build_default_connector_factory
from app.rules.registry import build_default_engine
from app.services.audit_service import AuditService


@pytest.mark.live
def test_cisco_ios_live_audit():
    host = os.environ.get("NETSENTRY_LIVE_HOST")
    username = os.environ.get("NETSENTRY_SSH_USERNAME")
    password = os.environ.get("NETSENTRY_SSH_PASSWORD")
    enable_secret = os.environ.get("NETSENTRY_ENABLE_SECRET")
    port = int(os.environ.get("NETSENTRY_LIVE_PORT", "22"))

    if not host or not username or not password:
        pytest.skip("Live test skipped: NETSENTRY_LIVE_HOST, NETSENTRY_SSH_USERNAME, or NETSENTRY_SSH_PASSWORD not set.")

    target = DeviceTarget(device_id="LIVE-ROUTER", host=host, platform="cisco_ios", port=port)
    credentials = Credentials(username=username, password=password, enable_secret=enable_secret)

    factory = build_default_connector_factory()
    engine = build_default_engine()
    service = AuditService(connector_factory=factory, engine=engine)

    result = service.audit_device(target, credentials)

    assert result.status == AuditStatus.COMPLETED
    assert len(result.findings) == 8
    assert result.pass_count + result.fail_count + result.unknown_count == 8
    assert not hasattr(result, "config_text")
