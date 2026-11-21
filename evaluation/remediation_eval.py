"""Remediation evaluation script for NetSentry (Spec Section 6).

Aggregates execution metrics from remediation_executions:
- Total executions, breakdown by mode (live, dry_run)
- Breakdown by result: VERIFIED, ROLLED_BACK, VERIFY_FAILED, FAILED
- needs_manual_attention count
- Success verification rate with Wilson 95% Confidence Interval
- Durations from started_at to finished_at
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.metrics import calculate_percentile, format_rate, wilson_score_interval


def evaluate_remediation_executions(db_path: Path) -> dict[str, Any]:
    """Calculate remediation execution metrics from database."""
    if not db_path.is_file():
        return {
            "error": f"Database file not found: {db_path}",
            "total_executions": 0,
            "live_executions": 0,
            "dry_run_executions": 0,
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        """
        SELECT id, plan_id, mode, started_at, finished_at, started_by,
               result, failure_code, changes_sent, persist_status, needs_manual_attention
        FROM remediation_executions
        ORDER BY id ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        return {
            "total_executions": 0,
            "live_executions": 0,
            "dry_run_executions": 0,
            "result_distribution": {},
            "failure_codes": {},
            "needs_manual_attention_count": 0,
            "verified_rate": "n/a",
            "verified_wilson_ci_95": "n/a",
            "execution_durations_seconds": {
                "min": "n/a",
                "median": "n/a",
                "p95": "n/a",
                "max": "n/a",
            },
        }

    live_rows = [r for r in rows if r["mode"] == "live"]
    dry_rows = [r for r in rows if r["mode"] == "dry_run"]

    result_counts: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    manual_attention_count = 0
    durations: list[float] = []

    for r in live_rows:
        res = r["result"]
        result_counts[res] = result_counts.get(res, 0) + 1

        if r["needs_manual_attention"]:
            manual_attention_count += 1

        fc = r["failure_code"]
        if fc:
            failure_counts[fc] = failure_counts.get(fc, 0) + 1

        if r["started_at"] and r["finished_at"]:
            try:
                t0 = datetime.fromisoformat(r["started_at"]).timestamp()
                t1 = datetime.fromisoformat(r["finished_at"]).timestamp()
                durations.append(max(0.0, t1 - t0))
            except Exception:
                pass

    durations.sort()
    verified_count = result_counts.get("VERIFIED", 0)
    live_count = len(live_rows)

    verified_ci = None
    if live_count > 0:
        low, high = wilson_score_interval(verified_count, live_count)
        verified_ci = [round(low, 4), round(high, 4)]

    return {
        "total_executions": total,
        "live_executions": live_count,
        "dry_run_executions": len(dry_rows),
        "result_distribution": result_counts,
        "failure_codes": failure_counts,
        "needs_manual_attention_count": manual_attention_count,
        "verified_rate": format_rate(verified_count / live_count if live_count > 0 else None),
        "verified_wilson_ci_95": verified_ci or "n/a",
        "execution_durations_seconds": {
            "min": round(min(durations), 2) if durations else "n/a",
            "median": round(calculate_percentile(durations, 50.0), 2) if durations else "n/a",
            "p95": round(calculate_percentile(durations, 95.0), 2) if durations else "n/a",
            "max": round(max(durations), 2) if durations else "n/a",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="NetSentry Remediation Evaluator")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "backend" / "netsentry.db", help="Path to sqlite DB")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    data = evaluate_remediation_executions(args.db)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print("=== NetSentry Remediation Executions Evaluation ===")
        print(f"Total Executions:   {data.get('total_executions', 0)}")
        print(f"Live Executions:    {data.get('live_executions', 0)}")
        print(f"Dry-run Executions: {data.get('dry_run_executions', 0)}")
        print(f"Results:            {data.get('result_distribution', {})}")
        print(f"Verified Rate:      {data.get('verified_rate', 'n/a')} (95% CI: {data.get('verified_wilson_ci_95', 'n/a')})")
        print(f"Needs Attention:    {data.get('needs_manual_attention_count', 0)}")
        durs = data.get("execution_durations_seconds", {})
        print(f"Duration (s):       min={durs.get('min')}, p50={durs.get('median')}, p95={durs.get('p95')}, max={durs.get('max')}")


if __name__ == "__main__":
    main()
