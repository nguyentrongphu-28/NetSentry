"""Performance evaluation script for NetSentry (Spec Section 6).

Aggregates execution runtimes from database (or exported sqlite file):
- Audit run duration: n, min, median (p50), p95, max
- Completed rate & error distribution
- Per-device metrics
- Standalone offline engine throughput (evaluated on corpus configs)
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.metrics import calculate_percentile, format_rate
from app.rules.registry import build_default_engine


def evaluate_audit_performance(
    db_path: Path,
    exclude_devices: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Calculate audit run statistics from NetSentry database."""
    if not db_path.is_file():
        return {
            "error": f"Database file not found: {db_path}",
            "total_runs": 0,
            "device_stats": {},
            "error_distribution": {},
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = """
    SELECT id, device_id, platform, status, started_at, finished_at, error_code
    FROM audit_runs
    """
    params = []
    if exclude_devices:
        placeholders = ",".join("?" for _ in exclude_devices)
        query += f" WHERE device_id NOT IN ({placeholders})"
        params.extend(exclude_devices)

    query += " ORDER BY id ASC"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    total_runs = len(rows)
    if total_runs == 0:
        return {
            "total_runs": 0,
            "completed_runs": 0,
            "completion_rate": "n/a",
            "durations_seconds": {
                "min": "n/a",
                "median": "n/a",
                "p95": "n/a",
                "max": "n/a",
            },
            "error_distribution": {},
            "device_stats": {},
        }

    completed_durations: list[float] = []
    error_counts: dict[str, int] = {}
    device_groups: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        dev_id = row["device_id"]
        status = row["status"]
        err_code = row["error_code"]

        if dev_id not in device_groups:
            device_groups[dev_id] = []

        duration = None
        if row["started_at"] and row["finished_at"]:
            try:
                t_start = datetime.fromisoformat(row["started_at"]).timestamp()
                t_end = datetime.fromisoformat(row["finished_at"]).timestamp()
                duration = max(0.0, t_end - t_start)
            except Exception:
                duration = None

        if status == "COMPLETED" and duration is not None:
            completed_durations.append(duration)
        elif status == "FAILED":
            err_key = err_code or "UNKNOWN_ERROR"
            error_counts[err_key] = error_counts.get(err_key, 0) + 1

        device_groups[dev_id].append({
            "status": status,
            "duration": duration,
            "error_code": err_code,
        })

    completed_runs = len(completed_durations)
    completed_durations.sort()

    overall_durations = {
        "min": min(completed_durations) if completed_durations else "n/a",
        "median": calculate_percentile(completed_durations, 50.0) if completed_durations else "n/a",
        "p95": calculate_percentile(completed_durations, 95.0) if completed_durations else "n/a",
        "max": max(completed_durations) if completed_durations else "n/a",
    }

    per_device_stats = {}
    for dev, runs in device_groups.items():
        dev_completed = [r["duration"] for r in runs if r["status"] == "COMPLETED" and r["duration"] is not None]
        dev_completed.sort()
        per_device_stats[dev] = {
            "total_runs": len(runs),
            "completed_runs": len(dev_completed),
            "completion_rate": format_rate(len(dev_completed) / len(runs) if runs else None),
            "durations_seconds": {
                "min": min(dev_completed) if dev_completed else "n/a",
                "median": calculate_percentile(dev_completed, 50.0) if dev_completed else "n/a",
                "p95": calculate_percentile(dev_completed, 95.0) if dev_completed else "n/a",
                "max": max(dev_completed) if dev_completed else "n/a",
            },
        }

    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "completion_rate": format_rate(completed_runs / total_runs if total_runs > 0 else None),
        "durations_seconds": overall_durations,
        "error_distribution": error_counts,
        "device_stats": per_device_stats,
    }


def evaluate_offline_engine_throughput(
    corpus_dir: Path,
    iterations: int = 100,
) -> dict[str, Any]:
    """Measure offline rule engine parsing and evaluation speed across configs."""
    configs = [p for p in corpus_dir.rglob("*.cfg") if p.is_file()]
    if not configs:
        return {"error": f"No config files found in {corpus_dir}"}

    engine = build_default_engine()

    latencies_ms: list[float] = []

    # Read all configs into memory first
    config_texts = [p.read_text(encoding="utf-8") for p in configs]

    for _ in range(iterations):
        for text in config_texts:
            t0 = time.perf_counter()
            _ = engine.run(text)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

    latencies_ms.sort()
    return {
        "configs_evaluated": len(configs),
        "iterations": iterations,
        "total_evaluations": len(latencies_ms),
        "latency_ms": {
            "min": round(min(latencies_ms), 3) if latencies_ms else "n/a",
            "median": round(calculate_percentile(latencies_ms, 50.0), 3) if latencies_ms else "n/a",
            "p95": round(calculate_percentile(latencies_ms, 95.0), 3) if latencies_ms else "n/a",
            "max": round(max(latencies_ms), 3) if latencies_ms else "n/a",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="NetSentry Performance Evaluator")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "backend" / "netsentry.db", help="Path to sqlite DB")
    parser.add_argument("--corpus", type=Path, default=REPO_ROOT / "evaluation" / "corpus" / "configs", help="Path to corpus configs")
    parser.add_argument("--exclude-device", action="append", default=[], help="Exclude devices by ID")
    parser.add_argument("--engine-only", action="store_true", help="Only measure offline engine throughput")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    result: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not args.engine_only:
        result["audit_performance"] = evaluate_audit_performance(
            args.db,
            exclude_devices=tuple(args.exclude_device),
        )

    if args.corpus.is_dir():
        result["engine_throughput"] = evaluate_offline_engine_throughput(args.corpus)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=== NetSentry Performance Evaluation ===")
        if "audit_performance" in result:
            ap = result["audit_performance"]
            print(f"Total Audit Runs: {ap.get('total_runs', 0)}")
            print(f"Completed Runs:   {ap.get('completed_runs', 0)} ({ap.get('completion_rate', 'n/a')})")
            durs = ap.get("durations_seconds", {})
            print(f"Audit Duration (s): min={durs.get('min')}, p50={durs.get('median')}, p95={durs.get('p95')}, max={durs.get('max')}")
            if ap.get("error_distribution"):
                print(f"Error Distribution: {ap['error_distribution']}")
        if "engine_throughput" in result:
            et = result["engine_throughput"]
            print("\n=== Offline Engine Throughput ===")
            lat = et.get("latency_ms", {})
            print(f"Total Evaluations: {et.get('total_evaluations', 0)}")
            print(f"Latency (ms): min={lat.get('min')}, p50={lat.get('median')}, p95={lat.get('p95')}, max={lat.get('max')}")


if __name__ == "__main__":
    main()
