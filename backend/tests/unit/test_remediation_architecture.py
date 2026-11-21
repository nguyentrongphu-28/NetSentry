"""Tests for architecture constraints, no-device-touch invariants, and config validation (Spec Sections 9.9 & 9.10)."""

import ast
from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.core.config import ConfigError, Settings
from app.domain.entities.device import Credentials, Device
from app.domain.entities.user import Role, User
from app.factories.connector_factory import ConnectorFactory
from app.repositories.database import init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.repositories.audit_repository import SqliteAuditRepository
from app.repositories.sqlite_remediation_repository import SqliteRemediationRepository
from app.repositories.sqlite_security_event_repository import SQLiteSecurityEventRepository
from app.repositories.sqlite_session_repository import SQLiteSessionRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher
from app.security.rate_limiter import InMemorySlidingWindowLimiter
from app.services.audit_service import AuditService
from app.services.audit_run_service import AuditRunService
from app.services.auth_service import AuthService
from app.services.remediation_service import RemediationService
from app.rules.registry import build_default_engine


# ---------------------------------------------------------------------------
# 9.9 Config Validation Tests
# ---------------------------------------------------------------------------


def test_public_mode_forces_require_distinct_approver():
    """In public mode, distinct approver must be forced to True even if configured as 0."""
    env = {
        "NETSENTRY_PUBLIC_MODE": "1",
        "NETSENTRY_ALLOWED_NETWORKS": "10.0.0.0/8",
        "NETSENTRY_REMEDIATION_REQUIRE_DISTINCT_APPROVER": "0",
        "NETSENTRY_API_KEY": "a" * 32,
    }
    settings = Settings.from_env(env)
    assert settings.public_mode is True
    assert settings.remediation_require_distinct_approver is True


@pytest.mark.parametrize(
    "env_key, bad_value",
    [
        ("NETSENTRY_REMEDIATION_PROPOSAL_TTL_MINUTES", "4"),       # min 5
        ("NETSENTRY_REMEDIATION_PROPOSAL_TTL_MINUTES", "1441"),    # max 1440
        ("NETSENTRY_REMEDIATION_PROPOSAL_TTL_MINUTES", "abc"),
        ("NETSENTRY_REMEDIATION_APPROVAL_TTL_MINUTES", "4"),       # min 5
        ("NETSENTRY_REMEDIATION_APPROVAL_TTL_MINUTES", "1441"),    # max 1440
        ("NETSENTRY_REMEDIATION_MAX_AUDIT_AGE_MINUTES", "0"),      # min 1
        ("NETSENTRY_REMEDIATION_MAX_AUDIT_AGE_MINUTES", "1441"),   # max 1440
    ],
)
def test_remediation_ttl_out_of_range_raises_config_error(env_key: str, bad_value: str):
    env = {
        env_key: bad_value,
        "NETSENTRY_API_KEY": "a" * 32,
    }
    with pytest.raises(ConfigError):
        Settings.from_env(env)


# ---------------------------------------------------------------------------
# 9.10 Architecture and AST Import Checking
# ---------------------------------------------------------------------------


FORBIDDEN_MODULE_SUBSTRINGS = (
    "connector",
    "factory",
    "client",
    "ai_",
    "netmiko",
    "paramiko",
    "urllib",
    "socket",
    "subprocess",
)


def _check_ast_imports(file_path: Path):
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.lower()
                for forbidden in FORBIDDEN_MODULE_SUBSTRINGS:
                    assert forbidden not in name, (
                        f"Forbidden import '{alias.name}' found in {file_path}"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").lower()
            for forbidden in FORBIDDEN_MODULE_SUBSTRINGS:
                assert forbidden not in mod, (
                    f"Forbidden from-import '{node.module}' found in {file_path}"
                )


def test_remediation_package_clean_architecture_ast():
    """Verify app/remediation/ and remediation_service.py have no forbidden imports."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    remediation_dir = repo_root / "app" / "remediation"
    for py_file in remediation_dir.glob("*.py"):
        _check_ast_imports(py_file)

    service_file = repo_root / "app" / "services" / "remediation_service.py"
    _check_ast_imports(service_file)


# ---------------------------------------------------------------------------
# 9.10 Zero Device Touch Invariant Test
# ---------------------------------------------------------------------------


class CountingConnector:
    """Mock connector that tracks connect() calls to prove devices are never touched."""

    def __init__(self, config_text: str):
        self.config_text = config_text
        self.connect_count = 0

    def connect(self) -> None:
        self.connect_count += 1

    def disconnect(self) -> None:
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def get_hostname(self) -> str:
        return "R1"

    def get_running_config(self) -> str:
        return self.config_text

    def send_command(self, cmd: str) -> str:
        return self.config_text


class CountingConnectorFactory(ConnectorFactory):
    def __init__(self, connector: CountingConnector):
        self.connector = connector

    def create(self, target, credentials):
        return self.connector


def test_zero_device_touch_during_remediation_lifecycle(tmp_path: Path):
    """Prove that proposing and approving remediation plans NEVER contacts the device."""
    db_file = tmp_path / "zero_touch.db"
    init_db(db_file)

    device_repo = SqliteDeviceRepository(db_file)
    audit_repo = SqliteAuditRepository(db_file)
    user_repo = SQLiteUserRepository(db_file)
    session_repo = SQLiteSessionRepository(db_file)
    event_repo = SQLiteSecurityEventRepository(db_file)
    remediation_repo = SqliteRemediationRepository(db_file)
    hasher = Argon2PasswordHasher()

    # Create users
    op_user = user_repo.add("op1", hasher.hash("OpPass123!"), Role.OPERATOR, must_change_password=False)
    adm_user = user_repo.add("adm1", hasher.hash("AdminPass123!"), Role.ADMIN, must_change_password=False)

    # Create device
    now = datetime.now(timezone.utc)
    dev = Device(
        device_id="r-zero-touch",
        name="Router Zero Touch",
        host="10.10.10.1",
        port=22,
        platform="cisco_ios",
        created_at=now,
        updated_at=now,
    )
    device_repo.add(dev)

    # Run audit using CountingConnector
    counting_conn = CountingConnector(config_text="hostname R1\nip http server\n")
    counting_factory = CountingConnectorFactory(counting_conn)
    audit_core = AuditService(connector_factory=counting_factory, engine=build_default_engine())
    audit_runner = AuditRunService(
        device_repository=device_repo,
        audit_repository=audit_repo,
        audit_service=audit_core,
    )

    run = audit_runner.run_audit("r-zero-touch", credentials=Credentials("admin", "cisco"))
    assert run.summary.status.value == "COMPLETED"
    # Audit connected once
    audit_connect_count = counting_conn.connect_count
    assert audit_connect_count == 1

    # Now initialize RemediationService WITHOUT any ConnectorFactory!
    auth_service = AuthService(
        user_repo=user_repo,
        session_repo=session_repo,
        event_repo=event_repo,
        password_hasher=hasher,
        rate_limiter=InMemorySlidingWindowLimiter(10, 60),
    )
    remediation_service = RemediationService(
        remediation_repo=remediation_repo,
        device_repo=device_repo,
        audit_repo=audit_repo,
        auth_service=auth_service,
        security_event_repo=event_repo,
        enabled=True,
    )

    # 1. Propose
    plan = remediation_service.propose(
        run_id=run.summary.id,
        rule_id="NET-008",
        proposer_username="op1",
        proposer_user_id=op_user.id,
        persist_after_verify=True,
    )
    assert plan.status.value == "PROPOSED"
    # Device was NOT touched
    assert counting_conn.connect_count == audit_connect_count

    # 2. Approve
    approved = remediation_service.approve(
        plan_id=plan.id,
        approver_username="adm1",
        approver_user_id=adm_user.id,
        approver_role=Role.ADMIN,
        password="AdminPass123!",
    )
    assert approved.status.value == "APPROVED"

    # CRITICAL INVARIANT: connect_count MUST STILL EQUAL audit_connect_count (no device touch!)
    assert counting_conn.connect_count == audit_connect_count, (
        f"Device was contacted {counting_conn.connect_count - audit_connect_count} times during remediation lifecycle!"
    )


def test_writer_and_connector_separation():
    """cisco_ios_writer and cisco_ios_connector must not import each other."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    writer_path = backend_dir / "app" / "connectors" / "cisco_ios_writer.py"
    reader_path = backend_dir / "app" / "connectors" / "cisco_ios_connector.py"

    writer_tree = ast.parse(writer_path.read_text(encoding="utf-8"))
    for node in ast.walk(writer_tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in getattr(node, "names", [])]
            mod = getattr(node, "module", "") or ""
            assert "cisco_ios_connector" not in mod
            assert not any("cisco_ios_connector" in n for n in names)

    reader_tree = ast.parse(reader_path.read_text(encoding="utf-8"))
    for node in ast.walk(reader_tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in getattr(node, "names", [])]
            mod = getattr(node, "module", "") or ""
            assert "cisco_ios_writer" not in mod
            assert not any("cisco_ios_writer" in n for n in names)

