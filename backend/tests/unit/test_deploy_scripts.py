"""Unit tests for deployment and launcher scripts validation."""

from pathlib import Path
import re
import subprocess
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
START_PUBLIC_SCRIPT = REPO_ROOT / "scripts" / "start_public.sh"
GITIGNORE_FILE = REPO_ROOT / ".gitignore"


def test_start_public_syntax():
    """Verify scripts/start_public.sh has valid bash syntax."""
    assert START_PUBLIC_SCRIPT.is_file()
    res = subprocess.run(["bash", "-n", str(START_PUBLIC_SCRIPT)], capture_output=True, text=True)
    assert res.returncode == 0, f"Bash syntax check failed:\n{res.stderr}"


def test_start_public_no_forbidden_patterns():
    """Ensure script does NOT contain insecure defaults, leaks, or hardcoded passwords."""
    content = START_PUBLIC_SCRIPT.read_text(encoding="utf-8")

    assert ":-live" not in content, "Found forbidden ':-live' in script"
    assert ":-dry_run" not in content, "Found forbidden ':-dry_run' in script"
    assert "AdminNetSentry" not in content, "Found leaked credential 'AdminNetSentry' in script"
    assert "default_pass" not in content, "Found 'default_pass' in script"
    assert "must_change_password=False" not in content, "Found 'must_change_password=False' in script"


def test_start_public_remediation_execute_mode_is_fixed_off():
    """Verify NETSENTRY_REMEDIATION_EXECUTE_MODE is strictly hardcoded to 'off'."""
    content = START_PUBLIC_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r'export\s+NETSENTRY_REMEDIATION_EXECUTE_MODE=["\']off["\']', content), (
        "Script must strictly export NETSENTRY_REMEDIATION_EXECUTE_MODE='off'"
    )


def test_start_public_allowed_networks_required_syntax():
    """Verify NETSENTRY_ALLOWED_NETWORKS requires manual declaration using :? parameter expansion."""
    content = START_PUBLIC_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r':\s*["\']?\$\{NETSENTRY_ALLOWED_NETWORKS:\?.*\}["\']?', content), (
        "Script must enforce ${NETSENTRY_ALLOWED_NETWORKS:?...} with :? expansion"
    )
    assert "10.0.0.0/8" not in content, "Script must not have overly broad 10.0.0.0/8 default"
    assert "172.16.0.0/12" not in content, "Script must not have overly broad 172.16.0.0/12 default"


def test_start_public_health_check_precedes_cloudflared_tunnel():
    """Verify health check logic executes before starting cloudflared tunnel."""
    content = START_PUBLIC_SCRIPT.read_text(encoding="utf-8")
    health_idx = content.find("/health")
    tunnel_idx = content.find("cloudflared tunnel")
    assert health_idx != -1, "Missing /health check in script"
    assert tunnel_idx != -1, "Missing cloudflared tunnel command in script"
    assert health_idx < tunnel_idx, "Health check must occur BEFORE running cloudflared tunnel"


def test_start_public_no_secret_echo_or_print():
    """Ensure script never echoes or prints variables holding secrets or passwords."""
    content = START_PUBLIC_SCRIPT.read_text(encoding="utf-8")
    for line in content.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("#"):
            continue
        if re.search(r'(echo|printf|print)\b.*(\$NETSENTRY_SSH_PASSWORD|\$NETSENTRY_ENABLE_SECRET|password|secret)', line_clean, re.IGNORECASE):
            pytest.fail(f"Found unsafe print of secret: {line_clean}")


def test_gitignore_contains_required_patterns():
    """Verify .gitignore includes db, sqlite, data, env, reports and keeps exceptions."""
    content = GITIGNORE_FILE.read_text(encoding="utf-8")
    assert "*.db" in content
    assert "*.sqlite" in content
    assert "data/" in content
    assert ".env" in content
    assert "!evaluation/corpus/**/*.cfg" in content
    assert "!backend/tests/fixtures/configs/*.cfg" in content


def test_no_adminnetsentry_in_any_script():
    """Ensure string 'AdminNetSentry' is completely eliminated from scripts/ directory."""
    scripts_dir = REPO_ROOT / "scripts"
    for script_file in scripts_dir.glob("*"):
        if script_file.is_file() and script_file.suffix in (".sh", ".py"):
            text = script_file.read_text(encoding="utf-8")
            assert "AdminNetSentry" not in text, f"Found 'AdminNetSentry' in {script_file.name}"
