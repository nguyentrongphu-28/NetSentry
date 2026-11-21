"""Rule Evaluation Tool for NetSentry.

Evaluates the rule engine accuracy against ground truth labeled configuration corpus.
Supports:
- Precision, Recall, F1 with Wilson 95% confidence intervals
- 3-class confusion matrix
- SHA-256 test split freeze and manifest verification
- Secret leakage detection in findings and evidence
- Output to console, JSON, and CSV
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

# Ensure backend and root are in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from app.rules.registry import build_default_engine
from evaluation.metrics import (
    BinaryConfusionMatrix,
    ThreeClassConfusionMatrix,
    format_rate,
    wilson_score_interval,
)

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
CONFIGS_DIR = CORPUS_DIR / "configs"
LABELS_PATH = CORPUS_DIR / "labels.json"
MANIFEST_PATH = CORPUS_DIR / "MANIFEST.sha256"


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_test_manifest() -> dict[str, str]:
    """Compute sha256 for all files in test split and test labels."""
    manifest = {}
    test_dir = CONFIGS_DIR / "test"
    if test_dir.is_dir():
        for p in sorted(test_dir.glob("*.cfg")):
            rel = f"test/{p.name}"
            manifest[rel] = compute_file_sha256(p)

    # Hash test section of labels.json
    if LABELS_PATH.is_file():
        with open(LABELS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        test_labels = {k: v for k, v in data.get("files", {}).items() if k.startswith("test/")}
        canonical_labels_str = json.dumps(test_labels, sort_keys=True)
        manifest["labels.json:test"] = hashlib.sha256(canonical_labels_str.encode("utf-8")).hexdigest()

    return manifest


def write_manifest(manifest: dict[str, str], path: Path = MANIFEST_PATH) -> None:
    lines = [f"{sha}  {fname}" for fname, sha in sorted(manifest.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_manifest(path: Path = MANIFEST_PATH) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"Manifest file missing: {path}"
    current = compute_test_manifest()
    expected = {}
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            expected[parts[1].strip()] = parts[0].strip()

    if current != expected:
        diffs = []
        for k in sorted(set(current.keys()) | set(expected.keys())):
            c_val = current.get(k)
            e_val = expected.get(k)
            if c_val != e_val:
                diffs.append(f"{k}: expected {e_val}, got {c_val}")
        return False, f"Manifest mismatch:\n  " + "\n  ".join(diffs)
    return True, "Manifest verified successfully."


def get_git_commit_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def evaluate_corpus(
    split: str = "test",
    custom_engine: Any = None,
) -> dict[str, Any]:
    if not LABELS_PATH.is_file():
        raise FileNotFoundError(f"labels.json not found at {LABELS_PATH}")

    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels_data = json.load(f)

    all_labels = labels_data.get("files", {})
    if split == "dev":
        target_files = {k: v for k, v in all_labels.items() if k.startswith("dev/")}
    elif split == "test":
        target_files = {k: v for k, v in all_labels.items() if k.startswith("test/")}
    else:
        target_files = all_labels

    engine = custom_engine or build_default_engine()

    rule_stats: dict[str, dict[str, int]] = {}
    rule_3class: dict[str, ThreeClassConfusionMatrix] = {}

    all_rule_ids = set()
    for file_rules in target_files.values():
        all_rule_ids.update(file_rules.keys())

    for r_id in sorted(all_rule_ids):
        rule_stats[r_id] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        rule_3class[r_id] = ThreeClassConfusionMatrix.empty()

    secret_sentinels_detected = []

    for rel_path, ground_truth in target_files.items():
        cfg_file = CONFIGS_DIR / rel_path
        if not cfg_file.is_file():
            raise FileNotFoundError(f"Configuration file not found: {cfg_file}")

        content = cfg_file.read_text(encoding="utf-8")
        findings = engine.run(content)

        # Detect any SENTINEL_ or plaintext leaks
        for finding in findings:
            for ev in finding.evidence:
                if "SENTINEL_" in ev or "-----BEGIN" in ev:
                    secret_sentinels_detected.append(f"{rel_path}:{finding.rule_id}:{ev}")

        pred_map = {f.rule_id: f.status.value for f in findings}

        for rule_id, label_spec in ground_truth.items():
            expected_status = label_spec["status"].upper()
            pred_status = pred_map.get(rule_id, "PASS")

            # Binary metrics: Positive = FAIL
            is_actual_fail = (expected_status == "FAIL")
            is_pred_fail = (pred_status == "FAIL")

            if is_actual_fail and is_pred_fail:
                rule_stats[rule_id]["tp"] += 1
            elif not is_actual_fail and is_pred_fail:
                rule_stats[rule_id]["fp"] += 1
            elif is_actual_fail and not is_pred_fail:
                rule_stats[rule_id]["fn"] += 1
            else:
                rule_stats[rule_id]["tn"] += 1

            rule_3class[rule_id] = rule_3class[rule_id].record(expected_status, pred_status)

    # Compile summary per rule
    results_by_rule = {}
    for rule_id in sorted(all_rule_ids):
        st = rule_stats[rule_id]
        bcm = BinaryConfusionMatrix(tp=st["tp"], fp=st["fp"], fn=st["fn"], tn=st["tn"])
        c3 = rule_3class[rule_id]

        p_wilson = wilson_score_interval(bcm.tp, bcm.tp + bcm.fp) if (bcm.tp + bcm.fp) > 0 else (0.0, 0.0)
        r_wilson = wilson_score_interval(bcm.tp, bcm.tp + bcm.fn) if (bcm.tp + bcm.fn) > 0 else (0.0, 0.0)

        results_by_rule[rule_id] = {
            "binary_cm": {"tp": bcm.tp, "fp": bcm.fp, "fn": bcm.fn, "tn": bcm.tn, "total": bcm.total},
            "precision": bcm.precision,
            "precision_formatted": format_rate(bcm.precision),
            "precision_wilson_95": [round(p_wilson[0], 4), round(p_wilson[1], 4)],
            "recall": bcm.recall,
            "recall_formatted": format_rate(bcm.recall),
            "recall_wilson_95": [round(r_wilson[0], 4), round(r_wilson[1], 4)],
            "f1": bcm.f1,
            "f1_formatted": format_rate(bcm.f1),
            "accuracy_3class": c3.accuracy,
            "accuracy_3class_formatted": format_rate(c3.accuracy),
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit_sha(),
        "split": split,
        "files_evaluated": len(target_files),
        "rules_evaluated": len(all_rule_ids),
        "results": results_by_rule,
        "secret_sentinels_detected": secret_sentinels_detected,
    }


def print_evaluation_table(eval_result: dict[str, Any]) -> None:
    print(f"\n=== NetSentry Rule Evaluation (Split: {eval_result['split']}) ===")
    print(f"Git Commit: {eval_result['git_commit']}")
    print(f"Files: {eval_result['files_evaluated']} | Timestamp: {eval_result['timestamp']}\n")

    header = f"{'Rule ID':<10} | {'TP':<4} {'FP':<4} {'FN':<4} {'TN':<4} | {'Precision':<10} | {'Recall':<10} | {'F1':<8} | {'3-Class Acc':<11}"
    print(header)
    print("-" * len(header))

    for r_id, d in sorted(eval_result["results"].items()):
        b = d["binary_cm"]
        print(
            f"{r_id:<10} | {b['tp']:<4} {b['fp']:<4} {b['fn']:<4} {b['tn']:<4} | "
            f"{d['precision_formatted']:<10} | {d['recall_formatted']:<10} | "
            f"{d['f1_formatted']:<8} | {d['accuracy_3class_formatted']:<11}"
        )
    print("-" * len(header))

    if eval_result["secret_sentinels_detected"]:
        print("\n[WARNING] Secrets or Sentinels Detected:")
        for s in eval_result["secret_sentinels_detected"]:
            print(f"  - {s}")
    else:
        print("\n[OK] No secret leakage or test sentinels detected in findings/evidence.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate NetSentry rule engine against corpus")
    parser.add_argument(
        "--split",
        choices=["test", "dev", "all"],
        default="test",
        help="Corpus split to evaluate (default: test)",
    )
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="Generate and freeze MANIFEST.sha256 for test split",
    )
    parser.add_argument(
        "--check-manifest",
        action="store_true",
        help="Verify MANIFEST.sha256 integrity only",
    )
    parser.add_argument("--json", dest="json_path", help="Save results to JSON file")
    parser.add_argument("--csv", dest="csv_path", help="Save results to CSV file")

    args = parser.parse_args()

    if args.freeze:
        manifest = compute_test_manifest()
        write_manifest(manifest)
        print(f"[OK] Test corpus frozen successfully: {MANIFEST_PATH} ({len(manifest)} items).")
        return 0

    if args.check_manifest or args.split == "test":
        ok, msg = verify_manifest()
        if not ok:
            print(f"[ERROR] {msg}", file=sys.stderr)
            return 1
        if args.check_manifest:
            print(f"[OK] {msg}")
            return 0

    eval_result = evaluate_corpus(split=args.split)
    print_evaluation_table(eval_result)

    if args.json_path:
        out_p = Path(args.json_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(eval_result, indent=2), encoding="utf-8")
        print(f"[OK] Saved JSON report to {out_p}")

    if args.csv_path:
        out_p = Path(args.csv_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        lines = ["rule_id,tp,fp,fn,tn,precision,recall,f1,accuracy_3class"]
        for r_id, d in sorted(eval_result["results"].items()):
            b = d["binary_cm"]
            lines.append(
                f"{r_id},{b['tp']},{b['fp']},{b['fn']},{b['tn']},"
                f"{d['precision_formatted']},{d['recall_formatted']},"
                f"{d['f1_formatted']},{d['accuracy_3class_formatted']}"
            )
        out_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[OK] Saved CSV report to {out_p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
