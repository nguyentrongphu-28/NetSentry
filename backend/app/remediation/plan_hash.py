"""Deterministic plan hash calculation for remediation plans."""

from __future__ import annotations

import hashlib
import json
from typing import Sequence


def compute_plan_hash(
    device_id: str,
    rule_id: str,
    template_id: str,
    template_version: int,
    commands: Sequence[str],
    persist_after_verify: bool,
) -> str:
    """Compute normalized SHA-256 hash of a remediation plan draft.

    Any change to target device, rule, template, commands or persist flag
    produces a completely different hash.
    """
    canonical_payload = {
        "commands": list(commands),
        "device_id": str(device_id),
        "persist_after_verify": bool(persist_after_verify),
        "rule_id": str(rule_id),
        "template_id": str(template_id),
        "template_version": int(template_version),
    }

    serialized = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
