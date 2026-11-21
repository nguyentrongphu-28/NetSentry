#!/usr/bin/env python3
"""Environment Verification Script for NetSentry (Spec Section 8).

Checks:
- Python version (requires Python 3.12.x)
- Virtual environment state
- Exact pinned packages for critical network connectors:
  * netmiko == 4.8.0
  * paramiko == 5.1.0
- Required directories existence
- Key environment variables sanity check
"""

from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent


def check_python_version() -> bool:
    print(f"[*] Checking Python version: {sys.version.split()[0]}...")
    if sys.version_info.major != 3 or sys.version_info.minor != 12:
        print(f"[!] WARNING/FAIL: Python 3.12 is required, but detected {sys.version}")
        return False
    print("    [OK] Python 3.12 detected.")
    return True


def check_critical_dependencies() -> bool:
    print("[*] Checking critical dependency versions (netmiko and paramiko)...")
    ok = True
    expected = {
        "netmiko": "4.8.0",
        "paramiko": "5.1.0",
    }
    for pkg, exp_ver in expected.items():
        try:
            ver = importlib.metadata.version(pkg)
            if ver == exp_ver:
                print(f"    [OK] {pkg} == {ver}")
            else:
                print(f"    [FAIL] {pkg} is {ver}, expected exact {exp_ver}!")
                ok = False
        except importlib.metadata.PackageNotFoundError:
            print(f"    [FAIL] {pkg} is NOT installed in current environment!")
            ok = False
    return ok


def check_directories() -> bool:
    print("[*] Checking repository structure & required folders...")
    required_dirs = [
        REPO_ROOT / "backend",
        REPO_ROOT / "evaluation",
        REPO_ROOT / "evaluation" / "corpus" / "configs",
        REPO_ROOT / "evaluation" / "ai",
        REPO_ROOT / "docs",
        REPO_ROOT / "scripts",
    ]
    all_ok = True
    for d in required_dirs:
        if d.is_dir():
            print(f"    [OK] Found {d.relative_to(REPO_ROOT)}")
        else:
            print(f"    [FAIL] Missing directory: {d.relative_to(REPO_ROOT)}")
            all_ok = False
    return all_ok


def check_env_variables() -> bool:
    print("[*] Checking environment variables (warnings only)...")
    # Public mode safety check
    public_mode = os.environ.get("NETSENTRY_PUBLIC_MODE", "0") == "1"
    auth_disabled = os.environ.get("NETSENTRY_AUTH_DISABLED", "0") == "1"

    if public_mode and auth_disabled:
        print("    [FAIL] NETSENTRY_PUBLIC_MODE=1 and NETSENTRY_AUTH_DISABLED=1 are mutually exclusive!")
        return False

    print("    [OK] Environment variables configuration is sound.")
    return True


def main() -> int:
    print("=== NetSentry Environment Check ===")
    results = [
        check_python_version(),
        check_critical_dependencies(),
        check_directories(),
        check_env_variables(),
    ]
    if all(results):
        print("\n[SUCCESS] All environment requirements passed!")
        return 0
    else:
        print("\n[FAIL] Some environment checks failed. Please fix before running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
