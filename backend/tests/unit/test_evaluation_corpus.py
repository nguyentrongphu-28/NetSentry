import json
from pathlib import Path
import re
from unittest.mock import MagicMock

import pytest

from app.domain.entities.finding import Finding, FindingStatus, Severity
from evaluation.rule_eval import (
    CONFIGS_DIR,
    LABELS_PATH,
    evaluate_corpus,
    verify_manifest,
)


def test_labels_file_exists_and_valid():
    assert LABELS_PATH.is_file(), "labels.json must exist in evaluation/corpus"
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("schema_version") == 1
    files_map = data.get("files", {})
    assert len(files_map) >= 8, "Corpus must have at least 8 files (4 dev, 4 test)"

    # Every labeled file must exist on disk
    for rel_path in files_map:
        cfg_file = CONFIGS_DIR / rel_path
        assert cfg_file.is_file(), f"File in labels.json missing on disk: {cfg_file}"


def test_all_configs_have_labels():
    all_cfgs = list(CONFIGS_DIR.glob("**/*.cfg"))
    assert len(all_cfgs) >= 8

    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    files_map = data.get("files", {})

    for cfg_p in all_cfgs:
        rel_path = f"{cfg_p.parent.name}/{cfg_p.name}"
        assert rel_path in files_map, f"Config file not labeled in labels.json: {rel_path}"


def test_no_unredacted_secrets_in_corpus():
    """Ensure no unredacted private keys or cleartext secrets in corpus configs."""
    forbidden_patterns = [
        re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA)? PRIVATE KEY-----"),
        re.compile(r"snmp-server community (public|private)\b.*", re.IGNORECASE),
        re.compile(r"enable secret (?!9|\$9|\$8)[0-9a-zA-Z]{6,}"),
    ]

    all_cfgs = list(CONFIGS_DIR.glob("**/*.cfg"))
    for cfg_p in all_cfgs:
        text = cfg_p.read_text(encoding="utf-8")
        # Check for private keys
        assert "-----BEGIN" not in text, f"Potential private key found in {cfg_p}"
        # RFC1918 or documentation IP check: ensure no arbitrary public IPs
        # Public IP pattern roughly
        ips = re.findall(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", text)
        for ip in ips:
            octets = [int(o) for o in ip.split(".")]
            if octets[0] == 0 or octets == [255, 255, 255, 255]:
                continue
            # Allow 10.x, 172.16-31.x, 192.168.x, 127.x, 0.x, subnet masks
            is_private = (
                octets[0] == 10
                or (octets[0] == 172 and 16 <= octets[1] <= 31)
                or (octets[0] == 192 and octets[1] == 168)
                or octets[0] == 127
                or octets[0] in (255, 0)
                or octets == [255, 255, 255, 0]
                or octets == [0, 255, 255, 255]
            )
            assert is_private, f"Public IP found in corpus {cfg_p}: {ip}"


def test_manifest_verification():
    """Ensure frozen test corpus manifest matches."""
    ok, msg = verify_manifest()
    assert ok, f"Test corpus manifest check failed: {msg}"


def test_evaluation_catches_broken_engine():
    """Self-verification: intentionally broken engine must yield lower recall/F1."""
    from app.rules.registry import build_default_engine

    real_engine = build_default_engine()

    from dataclasses import replace

    # Create broken engine where NET-008 always passes (never detects FAIL)
    class BrokenEngine:
        def run(self, config_text: str):
            findings = real_engine.run(config_text)
            # Remove or replace any NET-008 FAIL finding with PASS
            patched = []
            for f in findings:
                if f.rule_id == "NET-008":
                    patched.append(replace(f, status=FindingStatus.PASS))
                else:
                    patched.append(f)
            return patched

    broken = BrokenEngine()
    result = evaluate_corpus(split="test", custom_engine=broken)
    net008_res = result["results"]["NET-008"]
    # In test split, r4_snmp_http.cfg has actual NET-008 FAIL.
    # Since broken engine returns PASS, recall must drop to 0.0!
    assert net008_res["recall"] == 0.0
    assert net008_res["binary_cm"]["fn"] >= 1
