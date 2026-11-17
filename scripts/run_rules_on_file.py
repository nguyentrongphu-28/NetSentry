#!/usr/bin/env python3
"""NetSentry CLI script to audit a Cisco IOS configuration file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure backend/ is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rules.registry import build_default_engine  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run NetSentry Cisco IOS audit rules on a configuration file.",
    )
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to the Cisco IOS configuration file (.cfg).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output findings in JSON format.",
    )
    parser.add_argument(
        "--device-id",
        type=str,
        default=None,
        help="Identifier of the device being audited.",
    )
    return parser.parse_args()


def print_table(findings: list, device_id: str | None, file_path: Path) -> None:
    print("=" * 90)
    print(f" NetSentry Configuration Audit: {file_path.name}")
    if device_id:
        print(f" Device ID: {device_id}")
    print("=" * 90)
    print(f"{'RULE ID':<10} | {'STATUS':<8} | {'SEVERITY':<9} | {'TITLE':<45}")
    print("-" * 90)

    for f in findings:
        status_color = f.status
        print(f"{f.rule_id:<10} | {status_color:<8} | {f.severity:<9} | {f.title:<45}")
        if f.evidence:
            for ev in f.evidence:
                print(f"    Evidence: {ev}")

    print("=" * 90)
    pass_count = sum(1 for f in findings if f.status == "PASS")
    fail_count = sum(1 for f in findings if f.status == "FAIL")
    unk_count = sum(1 for f in findings if f.status == "UNKNOWN")
    print(f" Summary: {pass_count} PASS, {fail_count} FAIL, {unk_count} UNKNOWN (Total: {len(findings)})")
    print("=" * 90)


def main() -> int:
    args = parse_args()

    if not args.config_path.exists():
        print(f"Error: configuration file '{args.config_path}' not found.", file=sys.stderr)
        return 1

    config_text = args.config_path.read_text(encoding="utf-8")
    engine = build_default_engine()

    device_id = args.device_id or args.config_path.stem
    findings = engine.run(config_text, platform="cisco_ios", device_id=device_id)

    if args.as_json:
        data = [f.to_dict() for f in findings]
        print(json.dumps(data, indent=2))
    else:
        print_table(findings, device_id, args.config_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
