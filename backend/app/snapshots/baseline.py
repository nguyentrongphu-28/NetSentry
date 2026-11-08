# scripts/baseline.py
"""Baseline + phát hiện sai lệch (drift) giữa cấu hình và baseline, và giữa 2 snapshot.

Lưu ý quan trọng: snapshot đã bị che mật khẩu (<REDACTED>) nên việc ĐỔI mật khẩu
không thể phát hiện qua diff. Đây là giới hạn có chủ đích (ưu tiên không lưu bí mật).
"""
import json
import re
from collections import Counter

from app.audit.config_parser import get_interface_block, parse_config
from app.core.paths import RULES_DIR


def load_baseline(role_or_path):
    """Nhận 'switch'/'router' hoặc đường dẫn file JSON."""
    path = RULES_DIR / f"baseline_{role_or_path}.json" if role_or_path in ("switch", "router") else role_or_path
    with open(str(path), "r", encoding="utf-8") as f:
        return json.load(f)


def _rx(p):
    return re.compile(p, re.IGNORECASE)


def _drift(baseline, item_id, section, dtype, description, expected, actual):
    return {"baseline_id": baseline["baseline_id"], "item_id": item_id, "section": section,
            "type": dtype, "description": description, "expected": expected, "actual": actual}


def compare_to_baseline(config_text, baseline):
    """Trả về {'compliant': bool, 'drifts': [...]}."""
    parsed = parse_config(config_text)
    drifts = []

    for item in baseline.get("global_required", []):
        rx = _rx(item["pattern"])
        if not any(rx.search(l) for l in parsed.top_lines):
            drifts.append(_drift(baseline, item["id"], "global", "MISSING_REQUIRED",
                                 item["description"], item["pattern"], "không có"))
    for item in baseline.get("global_forbidden", []):
        rx = _rx(item["pattern"])
        for l in parsed.top_lines:
            if rx.search(l):
                drifts.append(_drift(baseline, item["id"], "global", "FORBIDDEN_PRESENT",
                                     item["description"], f"không có /{item['pattern']}/", l))

    for blk in baseline.get("blocks", []):
        brx = _rx(blk["block_pattern"])
        for b in (x for x in parsed.blocks if brx.search(x.header)):
            for req in blk.get("required", []):
                rx = _rx(req["pattern"])
                if not any(rx.search(c) for c in b.children):
                    drifts.append(_drift(baseline, blk["id"], b.header, "MISSING_REQUIRED",
                                         req["description"], req["pattern"], "không có"))
            for forb in blk.get("forbidden", []):
                rx = _rx(forb["pattern"])
                for c in b.children:
                    if rx.search(c):
                        drifts.append(_drift(baseline, blk["id"], b.header, "FORBIDDEN_PRESENT",
                                             forb["description"], f"không có /{forb['pattern']}/", c))

    for itf in baseline.get("interfaces", []):
        b = get_interface_block(parsed, itf["interface"])
        section = f"interface {itf['interface']}"
        if b is None:
            if not itf.get("optional"):
                drifts.append(_drift(baseline, itf["id"], section, "MISSING_SECTION",
                                     "Interface theo baseline không tồn tại", section, "không có"))
            continue
        for req in itf.get("required", []):
            rx = _rx(req["pattern"])
            if not any(rx.search(c) for c in b.children):
                drifts.append(_drift(baseline, itf["id"], section, "MISSING_REQUIRED",
                                     req["description"], req["pattern"], "không có"))
        for forb in itf.get("forbidden", []):
            rx = _rx(forb["pattern"])
            for c in b.children:
                if rx.search(c):
                    drifts.append(_drift(baseline, itf["id"], section, "FORBIDDEN_PRESENT",
                                         forb["description"], f"không có /{forb['pattern']}/", c))
    return {"baseline_id": baseline["baseline_id"], "compliant": not drifts, "drifts": drifts}


# ---------------------------------------------------------------------------
# So sánh 2 snapshot
# ---------------------------------------------------------------------------
def _sections(parsed):
    """header -> children (cùng header trùng nhau thì gộp)."""
    secs = {}
    for b in parsed.blocks:
        secs.setdefault(b.header, []).extend(b.children)
    return secs


def _variants(line):
    core = re.sub(r"^no\s+", "", line, flags=re.IGNORECASE)
    return {line, core, "no " + core}


def related_rules(section, line, rules):
    """Dòng thay đổi này chạm tới rule nào? (để đánh dấu 'liên quan bảo mật').
    Dùng 'touch_pattern' của rule (cùng họ lệnh) và cả pattern của từng check."""
    if not rules:
        return []
    variants = _variants(line)
    hits = []
    for r in rules:
        checks = r.get("checks", [])
        block_checks = [c for c in checks if c["type"] == "block_required"]
        try:
            # 1) cùng họ lệnh với rule (vd 'transport input telnet' chạm SEC-002)
            touch = r.get("touch_pattern")
            if touch and any(re.search(touch, v, re.IGNORECASE) for v in variants):
                if block_checks:
                    if section != "global" and any(re.search(c["block_pattern"], section, re.IGNORECASE) for c in block_checks):
                        hits.append(r["rule_id"])
                elif section == "global":
                    hits.append(r["rule_id"])
                continue
            # 2) khớp trực tiếp pattern của check
            for c in checks:
                if c["type"] in ("required_line", "forbidden_line"):
                    ok = section == "global"
                else:
                    ok = section != "global" and re.search(c["block_pattern"], section, re.IGNORECASE)
                if ok and any(re.search(c["pattern"], v, re.IGNORECASE) for v in variants):
                    hits.append(r["rule_id"])
        except re.error:
            continue
    return sorted(set(hits))


def _change(section, change, line, rules):
    rel = related_rules(section, line, rules)
    return {"section": section, "change": change, "line": line,
            "security_relevant": bool(rel), "related_rules": rel}


def diff_configs(old_text, new_text, rules=None):
    """So sánh 2 cấu hình (bỏ qua timestamp/dòng 'dễ đổi'). Trả về danh sách thay đổi."""
    old, new = _sections(parse_config(old_text)), _sections(parse_config(new_text))
    changes = []

    for header in sorted(set(old) | set(new)):
        o_children, n_children = old.get(header), new.get(header)
        if o_children is None or n_children is None:
            kids = n_children if o_children is None else o_children
            kind = "ADDED" if o_children is None else "REMOVED"
            if kids:  # khối có nội dung con
                rel = sorted({r for c in kids for r in related_rules(header, c, rules)})
                changes.append({"section": header, "change": f"SECTION_{kind}", "line": header,
                                "security_relevant": bool(rel), "related_rules": rel})
            else:     # dòng cấp 1 đơn lẻ
                changes.append(_change("global", kind, header, rules))
            continue
        added = Counter(n_children) - Counter(o_children)
        removed = Counter(o_children) - Counter(n_children)
        for line in sorted(added.elements()):
            changes.append(_change(header, "ADDED", line, rules))
        for line in sorted(removed.elements()):
            changes.append(_change(header, "REMOVED", line, rules))

    summary = {
        "total": len(changes),
        "added": sum(1 for c in changes if c["change"].endswith("ADDED")),
        "removed": sum(1 for c in changes if c["change"].endswith("REMOVED")),
        "security_relevant": sum(1 for c in changes if c["security_relevant"]),
    }
    return {"changed": bool(changes), "summary": summary, "changes": changes}
