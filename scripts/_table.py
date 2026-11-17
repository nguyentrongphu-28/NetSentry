"""Shared table printing utility for findings."""

from __future__ import annotations

from typing import Any, Sequence


def print_findings_table(findings: Sequence[Any], device_id: str | None, title: str) -> None:
    """Print findings formatted in a clear, readable tabular layout."""
    print("=" * 90)
    print(f" NetSentry Configuration Audit: {title}")
    if device_id:
        print(f" Device ID: {device_id}")
    print("=" * 90)
    print(f"{'RULE ID':<10} | {'STATUS':<8} | {'SEVERITY':<9} | {'TITLE':<45}")
    print("-" * 90)

    for f in findings:
        status = str(getattr(f, "status", ""))
        severity = str(getattr(f, "severity", ""))
        rule_id = str(getattr(f, "rule_id", ""))
        rule_title = str(getattr(f, "title", ""))
        print(f"{rule_id:<10} | {status:<8} | {severity:<9} | {rule_title:<45}")
        evidence = getattr(f, "evidence", ())
        if evidence:
            for ev in evidence:
                print(f"    Evidence: {ev}")

    print("=" * 90)
    pass_count = sum(1 for f in findings if str(getattr(f, "status", "")) == "PASS")
    fail_count = sum(1 for f in findings if str(getattr(f, "status", "")) == "FAIL")
    unk_count = sum(1 for f in findings if str(getattr(f, "status", "")) == "UNKNOWN")
    print(
        f" Summary: {pass_count} PASS, {fail_count} FAIL, {unk_count} UNKNOWN (Total: {len(findings)})"
    )
    print("=" * 90)
