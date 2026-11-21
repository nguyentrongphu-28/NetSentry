from __future__ import annotations

import difflib
import re
from typing import Sequence

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.audit_run import AuditRunDetail
from app.domain.entities.finding import Finding
from app.domain.entities.findings_diff import ChangeKind, FindingChange, FindingsDiff
from app.domain.entities.snapshot import ConfigDiff, ConfigSnapshot, DiffHunk, DiffLine
from app.domain.errors import DiffInputError

MAX_DIFF_LINES = 2000
_HUNK_RE = re.compile(r"^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@")

# Priority ordering for sorting finding changes
_KIND_ORDER = {
    ChangeKind.REGRESSION: 0,
    ChangeKind.PERSISTING: 1,
    ChangeKind.FIXED: 2,
    ChangeKind.OTHER: 3,
    ChangeKind.UNCHANGED_OK: 4,
}

_SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
    None: 5,
}


class DiffService:
    """Service providing configuration diffs and findings diffs between audit runs."""

    def config_diff(
        self,
        from_snapshot: ConfigSnapshot,
        to_snapshot: ConfigSnapshot,
        from_content: str,
        to_content: str,
    ) -> ConfigDiff:
        """Compute unified diff between two configuration snapshots."""
        if from_snapshot.device_id != to_snapshot.device_id:
            raise DiffInputError(
                f"Cannot diff snapshots from different devices: "
                f"'{from_snapshot.device_id}' vs '{to_snapshot.device_id}'"
            )

        # Check identical
        if (
            from_snapshot.content_sha256 == to_snapshot.content_sha256
            or from_content == to_content
        ):
            return ConfigDiff(
                from_run_id=from_snapshot.run_id,
                to_run_id=to_snapshot.run_id,
                identical=True,
                added=0,
                removed=0,
                hunks=(),
                truncated=False,
            )

        from_lines = from_content.splitlines()
        to_lines = to_content.splitlines()

        raw_diff = list(
            difflib.unified_diff(
                from_lines,
                to_lines,
                fromfile=f"run-{from_snapshot.run_id}",
                tofile=f"run-{to_snapshot.run_id}",
                lineterm="",
                n=3,
            )
        )

        # Skip the --- and +++ header lines
        diff_lines = [l for l in raw_diff if not l.startswith("---") and not l.startswith("+++")]

        total_lines = len(diff_lines)
        truncated = False
        if total_lines > MAX_DIFF_LINES:
            diff_lines = diff_lines[:MAX_DIFF_LINES]
            truncated = True

        hunks: list[DiffHunk] = []
        current_lines: list[DiffLine] = []
        old_start = 0
        new_start = 0
        added_count = 0
        removed_count = 0

        for line in diff_lines:
            if not line:
                continue
            hunk_match = _HUNK_RE.match(line)
            if hunk_match:
                if current_lines:
                    hunks.append(
                        DiffHunk(
                            old_start=old_start,
                            new_start=new_start,
                            lines=tuple(current_lines),
                        )
                    )
                    current_lines = []
                old_start = int(hunk_match.group(1))
                new_start = int(hunk_match.group(2))
            else:
                op = line[0]
                text = line[1:]
                if op == "+":
                    added_count += 1
                elif op == "-":
                    removed_count += 1
                elif op != " ":
                    op = " "
                    text = line
                current_lines.append(DiffLine(op=op, text=text))

        if current_lines:
            hunks.append(
                DiffHunk(
                    old_start=old_start,
                    new_start=new_start,
                    lines=tuple(current_lines),
                )
            )

        return ConfigDiff(
            from_run_id=from_snapshot.run_id,
            to_run_id=to_snapshot.run_id,
            identical=False,
            added=added_count,
            removed=removed_count,
            hunks=tuple(hunks),
            truncated=truncated,
        )

    def findings_diff(
        self,
        from_run: AuditRunDetail,
        to_run: AuditRunDetail,
    ) -> FindingsDiff:
        """Compute the difference in findings between two completed audit runs."""
        if from_run.summary.device_id != to_run.summary.device_id:
            raise DiffInputError(
                f"Audit runs belong to different devices: "
                f"'{from_run.summary.device_id}' vs '{to_run.summary.device_id}'"
            )

        if (
            from_run.summary.status != AuditStatus.COMPLETED
            or to_run.summary.status != AuditStatus.COMPLETED
        ):
            raise DiffInputError("Both audit runs must be COMPLETED to compute findings diff")

        if from_run.summary.id == to_run.summary.id:
            raise DiffInputError("Cannot diff an audit run with itself")

        before_map: dict[str, Finding] = {f.rule_id: f for f in from_run.findings}
        after_map: dict[str, Finding] = {f.rule_id: f for f in to_run.findings}

        all_rules = sorted(set(before_map.keys()) | set(after_map.keys()))
        changes: list[FindingChange] = []
        counts: dict[ChangeKind, int] = {k: 0 for k in ChangeKind}

        for rule_id in all_rules:
            b = before_map.get(rule_id)
            a = after_map.get(rule_id)

            b_stat = str(b.status) if b else None
            a_stat = str(a.status) if a else None
            b_sev = str(b.severity) if b else None
            a_sev = str(a.severity) if a else None
            title = a.title if a else (b.title if b else rule_id)

            # Classify kind
            if (b_stat in (None, "PASS")) and a_stat == "FAIL":
                kind = ChangeKind.REGRESSION
            elif b_stat == "FAIL" and a_stat == "PASS":
                kind = ChangeKind.FIXED
            elif b_stat == "FAIL" and a_stat == "FAIL":
                kind = ChangeKind.PERSISTING
            elif b_stat == "PASS" and a_stat == "PASS":
                kind = ChangeKind.UNCHANGED_OK
            else:
                kind = ChangeKind.OTHER

            counts[kind] += 1
            changes.append(
                FindingChange(
                    rule_id=rule_id,
                    title=title,
                    before_status=b_stat,
                    after_status=a_stat,
                    before_severity=b_sev,
                    after_severity=a_sev,
                    kind=kind,
                )
            )

        # Sort: REGRESSION > PERSISTING > FIXED > OTHER > UNCHANGED_OK, then severity, then rule_id
        def _sort_key(c: FindingChange):
            sev = c.after_severity or c.before_severity
            return (
                _KIND_ORDER.get(c.kind, 99),
                _SEVERITY_ORDER.get(sev, 99),
                c.rule_id,
            )

        changes.sort(key=_sort_key)

        return FindingsDiff(
            from_run_id=from_run.summary.id,
            to_run_id=to_run.summary.id,
            device_id=to_run.summary.device_id,
            changes=tuple(changes),
            counts=counts,
            has_previous=True,
        )

    def empty_findings_diff(self, to_run_id: int, device_id: str) -> FindingsDiff:
        """Return an empty findings diff for the first audit of a device."""
        return FindingsDiff(
            from_run_id=0,
            to_run_id=to_run_id,
            device_id=device_id,
            changes=(),
            counts={k: 0 for k in ChangeKind},
            has_previous=False,
        )
