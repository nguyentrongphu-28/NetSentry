"""Audit service coordinating device connection, configuration retrieval, and rule auditing."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Callable

from app.domain.entities.audit_result import AuditResult, AuditStatus
from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.errors import NetSentryError
from app.factories.connector_factory import ConnectorFactory
from app.rules.engine import RuleEngine

logger = logging.getLogger(__name__)


class AuditService:
    """Orchestrates device audits by connecting, collecting running configuration, and evaluating rules."""

    def __init__(
        self,
        connector_factory: ConnectorFactory,
        engine: RuleEngine,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.connector_factory = connector_factory
        self.engine = engine
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def audit_device(
        self,
        target: DeviceTarget,
        credentials: Credentials,
        *,
        on_config_collected: Callable[[str], None] | None = None,
    ) -> AuditResult:
        started_at = self.clock()
        try:
            connector = self.connector_factory.create(target, credentials)
            with connector:
                hostname = connector.get_hostname()
                config_text = connector.get_running_config()

                if on_config_collected is not None:
                    try:
                        on_config_collected(config_text)
                    except Exception as hook_exc:
                        logger.warning(
                            "on_config_collected hook failed for %s: %s",
                            target.host,
                            type(hook_exc).__name__,
                        )

                findings = self.engine.run(
                    config_text,
                    platform=target.platform,
                    device_id=target.device_id,
                )

            finished_at = self.clock()
            return AuditResult(
                device_id=target.device_id,
                platform=target.platform,
                status=AuditStatus.COMPLETED,
                started_at=started_at,
                finished_at=finished_at,
                findings=tuple(findings),
                hostname=hostname,
            )

        except NetSentryError as exc:
            logger.warning(
                "Audit failed for %s: [%s] %s",
                target.host,
                exc.code,
                exc,
            )
            finished_at = self.clock()
            return AuditResult(
                device_id=target.device_id,
                platform=target.platform,
                status=AuditStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                error_code=exc.code,
                error_message=str(exc),
                findings=(),
            )

        except (KeyboardInterrupt, SystemExit):
            raise

        except Exception:
            logger.exception("Unexpected error during audit for host %s", target.host)
            finished_at = self.clock()
            return AuditResult(
                device_id=target.device_id,
                platform=target.platform,
                status=AuditStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                error_code="INTERNAL_ERROR",
                error_message="Unexpected error during audit",
                findings=(),
            )
