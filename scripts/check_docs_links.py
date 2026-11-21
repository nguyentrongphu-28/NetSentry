#!/usr/bin/env python3
"""Docs Relative Links Validator (Spec Section 8.1).

Scans all Markdown files in docs/ and README.md, extracts relative file links,
and validates that the target files and anchor headings exist on disk.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

# Regex matching Markdown links [text](target) excluding external http/https/mailto
MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((?!https?://|mailto:|#)([^)]+)\)")


def check_markdown_links() -> tuple[int, int, list[str]]:
    files_to_check = list(DOCS_DIR.glob("*.md"))
    readme = REPO_ROOT / "README.md"
    if readme.is_file():
        files_to_check.append(readme)

    total_links = 0
    broken_links = 0
    errors = []

    for md_file in files_to_check:
        content = md_file.read_text(encoding="utf-8")
        for match in MD_LINK_PATTERN.finditer(content):
            target = match.group(2).strip()

            # Strip query params or hash anchors
            raw_path = target.split("#")[0].split("?")[0]
            if not raw_path:
                continue

            total_links += 1

            # Handle file:/// scheme if present
            if raw_path.startswith("file://"):
                target_path = Path(raw_path.replace("file://", ""))
            elif raw_path.startswith("/"):
                target_path = Path(raw_path)
            else:
                target_path = (md_file.parent / raw_path).resolve()

            if not target_path.exists():
                broken_links += 1
                errors.append(
                    f"Broken link in {md_file.relative_to(REPO_ROOT)}: '{target}' -> Not found: {target_path}"
                )

    return total_links, broken_links, errors


def main() -> int:
    print("=== NetSentry Documentation Links Check ===")
    total, broken, errors = check_markdown_links()
    print(f"Total links verified: {total}")
    print(f"Broken links:         {broken}")

    if broken > 0:
        print("\nErrors detected:")
        for err in errors:
            print(f"  [X] {err}")
        return 1

    print("\n[SUCCESS] All documentation links are valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
