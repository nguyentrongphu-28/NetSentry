"""Drift comparison service.

Compares normalized, redacted Cisco IOS configuration against an active baseline.
"""

from __future__ import annotations

import difflib
import hashlib
from app.domain.entities.drift import BlockChange, BlockChangeKind, DriftReport, DriftSummary
from app.services.config_blocks import split_blocks

SECURITY_PREFIXES: tuple[str, ...] = (
    "line vty",
    "line con",
    "line aux",
    "aaa",
    "username",
    "enable",
    "snmp-server",
    "ip ssh",
    "ip http",
    "access-list",
    "ip access-list",
    "crypto",
    "service",
    "banner",
    "ntp authentication",
    "logging",
)


def _is_security_relevant(key: str, changed_lines: tuple[str, ...]) -> bool:
    lower_key = key.lower()
    for prefix in SECURITY_PREFIXES:
        if lower_key.startswith(prefix):
            return True

    # For (global) block or general blocks, check added/removed lines
    for line in changed_lines:
        line_lower = line.strip().lower()
        if line_lower.startswith("no "):
            line_lower = line_lower[3:].strip()
        for prefix in SECURITY_PREFIXES:
            if line_lower.startswith(prefix):
                return True
    return False


class DriftService:
    """Service to compute block-level drift between baseline and current configuration."""

    def __init__(self, max_blocks: int = 500) -> None:
        self._max_blocks = max_blocks

    def compare(
        self,
        *,
        device_id: str,
        baseline_id: int,
        run_id: int,
        baseline_text: str,
        current_text: str,
        include_lines: bool = True,
    ) -> DriftReport:
        """Compare baseline and current configuration texts."""
        base_hash = hashlib.sha256(baseline_text.encode("utf-8")).hexdigest()
        curr_hash = hashlib.sha256(current_text.encode("utf-8")).hexdigest()

        if base_hash == curr_hash:
            summary = DriftSummary(
                status="IN_SYNC",
                added_blocks=0,
                removed_blocks=0,
                changed_blocks=0,
                security_relevant_count=0,
            )
            return DriftReport(
                device_id=device_id,
                baseline_id=baseline_id,
                run_id=run_id,
                lines_included=include_lines,
                summary=summary,
                blocks=(),
                truncated=False,
            )

        base_blocks = split_blocks(baseline_text)
        curr_blocks = split_blocks(current_text)

        all_keys = set(base_blocks.keys()) | set(curr_blocks.keys())
        changes: list[BlockChange] = []

        added_blocks_count = 0
        removed_blocks_count = 0
        changed_blocks_count = 0
        security_relevant_count = 0

        for key in sorted(all_keys):
            in_base = key in base_blocks
            in_curr = key in curr_blocks

            if not in_base and in_curr:
                # ADDED block
                curr_lines = curr_blocks[key]
                added_tuple = tuple(curr_lines) if include_lines else ()
                sec_rel = _is_security_relevant(key, tuple(curr_lines))
                changes.append(
                    BlockChange(
                        key=key,
                        kind=BlockChangeKind.ADDED,
                        security_relevant=sec_rel,
                        added_lines=added_tuple,
                        removed_lines=(),
                        added_count=len(curr_lines),
                        removed_count=0,
                    )
                )
                added_blocks_count += 1
                if sec_rel:
                    security_relevant_count += 1

            elif in_base and not in_curr:
                # REMOVED block
                base_lines = base_blocks[key]
                removed_tuple = tuple(base_lines) if include_lines else ()
                sec_rel = _is_security_relevant(key, tuple(base_lines))
                changes.append(
                    BlockChange(
                        key=key,
                        kind=BlockChangeKind.REMOVED,
                        security_relevant=sec_rel,
                        added_lines=(),
                        removed_lines=removed_tuple,
                        added_count=0,
                        removed_count=len(base_lines),
                    )
                )
                removed_blocks_count += 1
                if sec_rel:
                    security_relevant_count += 1

            else:
                # Both present: check if CHANGED
                base_lines = base_blocks[key]
                curr_lines = curr_blocks[key]

                if key == "(global)":
                    # Compare as set (order does not matter for global lines)
                    base_set = set(base_lines)
                    curr_set = set(curr_lines)

                    if base_set != curr_set:
                        added_items = [x for x in curr_lines if x not in base_set]
                        removed_items = [x for x in base_lines if x not in curr_set]
                        changed_lines = tuple(added_items + removed_items)
                        sec_rel = _is_security_relevant(key, changed_lines)

                        changes.append(
                            BlockChange(
                                key=key,
                                kind=BlockChangeKind.CHANGED,
                                security_relevant=sec_rel,
                                added_lines=tuple(added_items) if include_lines else (),
                                removed_lines=tuple(removed_items) if include_lines else (),
                                added_count=len(added_items),
                                removed_count=len(removed_items),
                            )
                        )
                        changed_blocks_count += 1
                        if sec_rel:
                            security_relevant_count += 1
                else:
                    # Ordered comparison
                    if base_lines != curr_lines:
                        matcher = difflib.SequenceMatcher(None, base_lines, curr_lines)
                        added_items: list[str] = []
                        removed_items: list[str] = []

                        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                            if tag in ("delete", "replace"):
                                removed_items.extend(base_lines[i1:i2])
                            if tag in ("insert", "replace"):
                                added_items.extend(curr_lines[j1:j2])

                        changed_lines = tuple(added_items + removed_items)
                        sec_rel = _is_security_relevant(key, changed_lines)

                        changes.append(
                            BlockChange(
                                key=key,
                                kind=BlockChangeKind.CHANGED,
                                security_relevant=sec_rel,
                                added_lines=tuple(added_items) if include_lines else (),
                                removed_lines=tuple(removed_items) if include_lines else (),
                                added_count=len(added_items),
                                removed_count=len(removed_items),
                            )
                        )
                        changed_blocks_count += 1
                        if sec_rel:
                            security_relevant_count += 1

        # Sorting: security_relevant first, then CHANGED > ADDED > REMOVED, then key
        kind_order = {
            BlockChangeKind.CHANGED: 0,
            BlockChangeKind.ADDED: 1,
            BlockChangeKind.REMOVED: 2,
        }

        changes.sort(key=lambda c: (not c.security_relevant, kind_order[c.kind], c.key))

        truncated = len(changes) > self._max_blocks
        if truncated:
            changes = changes[: self._max_blocks]

        is_drifted = (added_blocks_count + removed_blocks_count + changed_blocks_count) > 0
        status = "DRIFTED" if is_drifted else "IN_SYNC"

        summary = DriftSummary(
            status=status,
            added_blocks=added_blocks_count,
            removed_blocks=removed_blocks_count,
            changed_blocks=changed_blocks_count,
            security_relevant_count=security_relevant_count,
        )

        return DriftReport(
            device_id=device_id,
            baseline_id=baseline_id,
            run_id=run_id,
            lines_included=include_lines,
            summary=summary,
            blocks=tuple(changes),
            truncated=truncated,
        )
