# scripts/rule_engine.py
"""Rule engine tham chiếu của Thành viên A (B có thể bọc lại thành service).

Đầu vào : văn bản cấu hình (đã làm sạch) + thông tin thiết bị.
Đầu ra  : danh sách finding theo schema chung của nhóm:
          rule_id, device_id, title, severity, status, evidence, rationale,
          remediation, checked_at   (+ device_name)
status ∈ PASS | FAIL | NOT_APPLICABLE | ERROR
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone

from app.audit.config_parser import parse_config
from app.core.paths import RULES_PATH

CHECK_TYPES = ("required_line", "forbidden_line", "block_required")
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _rx(p):
    return re.compile(p, re.IGNORECASE)


def load_rules(path=None):
    with open(str(path or RULES_PATH), "r", encoding="utf-8") as f:
        return json.load(f)


def validate_rules(rules):
    """Kiểm tra file rule: trả về danh sách lỗi (rỗng nếu ổn)."""
    errors, seen = [], set()
    for r in rules:
        rid = r.get("rule_id", "<thiếu rule_id>")
        if rid in seen:
            errors.append(f"{rid}: trùng rule_id")
        seen.add(rid)
        for k in ("name", "severity", "description", "checks", "remediation"):
            if not r.get(k):
                errors.append(f"{rid}: thiếu '{k}'")
        if r.get("severity") not in SEVERITY_ORDER:
            errors.append(f"{rid}: severity không hợp lệ")
        for c in r.get("checks", []):
            if c.get("type") not in CHECK_TYPES:
                errors.append(f"{rid}: loại check không hỗ trợ '{c.get('type')}'")
            for key in ("pattern", "block_pattern", "only_if", "exclude_header"):
                if key in c:
                    try:
                        re.compile(c[key])
                    except re.error as e:
                        errors.append(f"{rid}: regex '{key}' lỗi ({e})")
    return errors


# ---- từng loại check: trả về (status, evidence[list]) -----------------------
def _check_required_line(parsed, c):
    rx = _rx(c["pattern"])
    hits = [l for l in parsed.top_lines if rx.search(l)]
    if hits:
        return "PASS", [f"Tìm thấy: {hits[0]}"]
    return "FAIL", [f"Không có dòng cấu hình khớp /{c['pattern']}/"]


def _check_forbidden_line(parsed, c):
    rx = _rx(c["pattern"])
    hits = [l for l in parsed.top_lines if rx.search(l)]
    if hits:
        return "FAIL", [f"Phát hiện dòng không được phép: {h}" for h in hits]
    return "PASS", [f"Không có dòng nào khớp /{c['pattern']}/ (đã tắt hoặc không tồn tại)"]


def _check_block_required(parsed, c):
    block_rx, pat_rx = _rx(c["block_pattern"]), _rx(c["pattern"])
    only_rx = _rx(c["only_if"]) if c.get("only_if") else None
    excl_rx = _rx(c["exclude_header"]) if c.get("exclude_header") else None
    evidence, failed, eligible = [], False, 0
    for b in parsed.blocks:
        if not block_rx.search(b.header) or (excl_rx and excl_rx.search(b.header)):
            continue
        if only_rx and not any(only_rx.search(ch) for ch in b.children):
            continue
        eligible += 1
        hit = next((ch for ch in b.children if pat_rx.search(ch)), None)
        if hit:
            evidence.append(f"[{b.header}] OK: {hit}")
        else:
            failed = True
            evidence.append(f"[{b.header}] thiếu dòng khớp /{c['pattern']}/")
    if eligible == 0:
        return "NOT_APPLICABLE", ["Không có khối cấu hình phù hợp để kiểm tra"]
    return ("FAIL" if failed else "PASS"), evidence


_DISPATCH = {
    "required_line": _check_required_line,
    "forbidden_line": _check_forbidden_line,
    "block_required": _check_block_required,
}


def evaluate_rule(parsed, rule):
    statuses, evidence = [], []
    for c in rule["checks"]:
        try:
            st, ev = _DISPATCH[c["type"]](parsed, c)
        except Exception as e:  # noqa: BLE001
            st, ev = "ERROR", [f"Lỗi khi chạy check: {e}"]
        statuses.append(st)
        evidence.extend(ev)
    if "ERROR" in statuses:
        return "ERROR", evidence
    if "FAIL" in statuses:
        return "FAIL", evidence
    if all(s == "NOT_APPLICABLE" for s in statuses):
        return "NOT_APPLICABLE", evidence
    return "PASS", evidence


def evaluate_config(config_text, device=None, rules=None, checked_at=None):
    """Chạy toàn bộ rule lên một cấu hình. Rule không hợp với role thiết bị -> NOT_APPLICABLE."""
    device = device or {}
    rules = rules if rules is not None else load_rules()
    parsed = parse_config(config_text)
    now = (checked_at or datetime.now(timezone.utc)).isoformat()
    role = device.get("role")
    findings = []
    for r in rules:
        roles = r.get("applies_to", {}).get("roles")
        if role and roles and role not in roles:
            status, evidence = "NOT_APPLICABLE", [f"Rule không áp dụng cho role '{role}'"]
        else:
            status, evidence = evaluate_rule(parsed, r)
        findings.append({
            "rule_id": r["rule_id"],
            "device_id": device.get("id"),
            "device_name": device.get("name"),
            "title": r["name"],
            "severity": r["severity"],
            "status": status,
            "evidence": evidence,
            "rationale": r["description"],
            "remediation": r["remediation"],
            "checked_at": now,
        })
    return findings


def summarize(findings):
    s = {"total": len(findings), "pass": 0, "fail": 0, "not_applicable": 0, "error": 0,
         "fail_by_severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}
    for f in findings:
        key = f["status"].lower()
        s[key] = s.get(key, 0) + 1
        if f["status"] == "FAIL":
            s["fail_by_severity"][f["severity"]] += 1
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description="Chạy rule audit lên một file cấu hình")
    ap.add_argument("config", help="Đường dẫn file cấu hình (.cfg)")
    ap.add_argument("--role", choices=("router", "switch"))
    ap.add_argument("--json", action="store_true", help="In JSON thay vì bảng")
    args = ap.parse_args(argv)
    with open(args.config, "r", encoding="utf-8") as f:
        text = f.read()
    findings = evaluate_config(text, {"id": "cli", "name": args.config, "role": args.role})
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda x: (x["status"] != "FAIL", SEVERITY_ORDER[x["severity"]], x["rule_id"])):
            print(f"{f['status']:<15}{f['severity']:<8}{f['rule_id']}  {f['title']}")
            if f["status"] == "FAIL":
                for e in f["evidence"]:
                    print(f"      - {e}")
        print(summarize(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
