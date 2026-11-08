"""Giải thích dự phòng, hoàn toàn từ rules.json + evidence: dùng khi LLM lỗi/timeout/trả sai schema.
Nhờ vậy hệ thống vẫn dùng được khi không có API key và không bao giờ trả nội dung LLM chưa được kiểm tra."""
from .guards import check_command_line, collapse_ws, fold

_TEXT = {
    "vi": {
        "answer": "Phát hiện {rule_id} ({severity}): {title}. {description}",
        "impact": "Áp dụng các lệnh gợi ý có thể thay đổi cách thiết bị chấp nhận kết nối/quản trị. "
                  "Hãy lưu cấu hình hiện tại trước, thử trong khung giờ bảo trì và kiểm tra lại bằng scan mới.",
    },
    "en": {
        "answer": "Finding {rule_id} ({severity}): {title}. {description}",
        "impact": "Applying the suggested commands may change how the device accepts management connections. "
                  "Save the current config first, apply during a maintenance window and re-scan to verify.",
    },
}


def build_fallback_reply(finding: dict, rule: dict, language: str = "vi") -> dict:
    t = _TEXT.get(language, _TEXT["vi"])
    desc = (rule or {}).get("description", "")
    evidence = [str(x) for x in finding.get("evidence", []) if str(x).strip()]
    steps = []
    # Dòng remediation do chính rules.json (nguồn tin cậy của A) định nghĩa được phép hiển thị nguyên vẹn
    # (vd. nội dung banner, placeholder 'interface <tên-interface>'); vẫn bị chặn nếu chứa bí mật/lệnh nguy hiểm.
    trusted = frozenset(fold(collapse_ws(x)) for x in (rule or {}).get("remediation", []))
    for line in (rule or {}).get("remediation", []):
        ok, _ = check_command_line(line, trusted)
        if ok:
            steps.append(collapse_ws(line))
    return {
        "answer": t["answer"].format(rule_id=finding.get("rule_id", ""), severity=finding.get("severity", ""),
                                     title=finding.get("title", ""), description=desc)[:1500],
        "why_it_matters": desc[:1000],
        "evidence_used": [{"rule_id": finding.get("rule_id", ""), "quote": collapse_ws(evidence[0])[:300]}] if evidence else [],
        "risk_level": finding.get("severity") if finding.get("severity") in {"LOW", "MEDIUM", "HIGH"} else None,
        "impact_of_fix": t["impact"],
        "manual_steps": steps,
        "proposed_action": None,
        "confidence": "medium",
        "insufficient_data": not evidence,
        "injection_noticed": False,
    }
