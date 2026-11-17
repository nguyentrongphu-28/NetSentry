from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.domain.interfaces.audit_rule import AuditRule
from app.rules.engine import RuleEngine
from app.rules.http_server_rule import HttpServerRule
from app.rules.ios_config_parser import IosConfigParser
from app.rules.password_rule import (
    PasswordEncryptionServiceRule,
    PlainTextCredentialRule,
)
from app.rules.snmp_rule import SnmpCommunityRule
from app.rules.ssh_rule import SshVersionRule
from app.rules.telnet_rule import TelnetRule
from app.rules.vty_acl_rule import VtyAccessClassRule
from app.rules.vty_timeout_rule import VtyExecTimeoutRule


def get_default_rules() -> list[AuditRule]:
    """Return the 8 standard Cisco IOS audit rules in order (NET-001 through NET-008)."""
    return [
        TelnetRule(),  # NET-001
        SshVersionRule(),  # NET-002
        PlainTextCredentialRule(),  # NET-003
        PasswordEncryptionServiceRule(),  # NET-004
        VtyExecTimeoutRule(),  # NET-005
        VtyAccessClassRule(),  # NET-006
        SnmpCommunityRule(),  # NET-007
        HttpServerRule(),  # NET-008
    ]


def build_default_engine(
    clock: Callable[[], datetime] | None = None,
) -> RuleEngine:
    """Build a default RuleEngine instance pre-configured with Cisco IOS parser and rules."""
    return RuleEngine(
        rules=get_default_rules(),
        parser=IosConfigParser(),
        clock=clock,
    )
