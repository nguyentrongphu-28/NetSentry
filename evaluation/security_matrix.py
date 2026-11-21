"""Security Test Matrix Runner for NetSentry.

Parses evaluation/security_matrix.yaml, executes the mapped pytest nodes,
and produces a structured verification report (docs/security_test_results.md).
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
YAML_PATH = Path(__file__).resolve().parent / "security_matrix.yaml"
OUTPUT_MD_PATH = REPO_ROOT / "docs" / "security_test_results.md"


def load_matrix(path: Path = YAML_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Matrix definition not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_single_test(node_id: str) -> bool:
    """Run a single pytest node from backend/ directory."""
    cmd = [
        str(REPO_ROOT / ".venv" / "bin" / "pytest"),
        "-q",
        f"backend/{node_id}",
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED: {node_id}\n{res.stdout}\n{res.stderr}")
    return res.returncode == 0


def run_security_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    reqs = matrix.get("requirements", {})
    results = {}
    total_tests_run = 0
    total_passed = 0
    total_failed = 0
    gaps_found = 0

    for code, spec in sorted(reqs.items()):
        tests = spec.get("tests", [])
        if not tests:
            gaps_found += 1
            results[code] = {
                "title": spec.get("title", ""),
                "source": spec.get("source", ""),
                "total": 0,
                "passed": 0,
                "failed": 0,
                "status": "GAP",
                "tests": [],
            }
            continue

        req_passed = 0
        req_failed = 0
        test_details = []

        for t_node in tests:
            passed = run_single_test(t_node)
            total_tests_run += 1
            if passed:
                req_passed += 1
                total_passed += 1
            else:
                req_failed += 1
                total_failed += 1
            test_details.append({"node": t_node, "passed": passed})

        status = "PASS" if req_failed == 0 else "FAIL"
        results[code] = {
            "title": spec.get("title", ""),
            "source": spec.get("source", ""),
            "total": len(tests),
            "passed": req_passed,
            "failed": req_failed,
            "status": status,
            "tests": test_details,
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_requirements": len(reqs),
        "total_tests_run": total_tests_run,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "gaps_found": gaps_found,
        "requirements": results,
    }


def generate_markdown_report(data: dict[str, Any]) -> str:
    lines = [
        "# NetSentry Security Verification Matrix (S1–S15)",
        "",
        f"- **Thời điểm kiểm tra**: `{data['timestamp']}`",
        f"- **Tổng số yêu cầu**: `{data['total_requirements']}`",
        f"- **Tổng số test nodes thực thi**: `{data['total_tests_run']}` (Đạt: `{data['total_passed']}`, Trượt: `{data['total_failed']}`)",
        f"- **Số lượng khoảng trống (GAPs)**: `{data['gaps_found']}`",
        "",
        "| Mã | Yêu cầu an toàn | Nguồn | Số test | Đạt | Trượt | Trạng thái |",
        "| :---: | :--- | :--- | :---: | :---: | :---: | :---: |",
    ]

    for code, d in sorted(data["requirements"].items()):
        status_badge = "✅ ĐẠT" if d["status"] == "PASS" else ("⚠️ GAP" if d["status"] == "GAP" else "❌ TRƯỢT")
        lines.append(
            f"| **{code}** | {d['title']} | {d['source']} | {d['total']} | {d['passed']} | {d['failed']} | {status_badge} |"
        )

    lines.extend([
        "",
        "## Chi Tiết Bằng Chứng Kiểm Thử (Pytest Node Traceability)",
        "",
    ])

    for code, d in sorted(data["requirements"].items()):
        lines.append(f"### {code}: {d['title']}")
        if not d["tests"]:
            lines.append("- *(Chưa có test case - GAP)*")
        else:
            for t in d["tests"]:
                icon = "✓" if t["passed"] else "✗"
                lines.append(f"- `{icon}` `{t['node']}`")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NetSentry Security Verification Matrix")
    parser.add_argument("--out", help="Path to write markdown results", default=str(OUTPUT_MD_PATH))
    args = parser.parse_args()

    print(f"Loading security matrix from {YAML_PATH}...")
    matrix = load_matrix()

    print(f"Executing {len(matrix.get('requirements', {}))} security requirements tests...")
    result_data = run_security_matrix(matrix)

    md_report = generate_markdown_report(result_data)
    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(md_report, encoding="utf-8")
    print(f"[OK] Report written to {out_p}\n")

    print(f"Summary: {result_data['total_passed']}/{result_data['total_tests_run']} tests passed. Gaps: {result_data['gaps_found']}")
    if result_data["total_failed"] > 0 or result_data["gaps_found"] > 0:
        print("[FAIL] Security matrix has failures or gaps.", file=sys.stderr)
        return 1

    print("[SUCCESS] All security requirements S1–S15 PASSED!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
