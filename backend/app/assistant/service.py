"""Điều phối: gate xác định -> (LLM) -> validator -> fallback. Không có đường tới thiết bị."""
import hashlib
import json
import re
from datetime import datetime, timezone

from .fallback import build_fallback_reply
from .guards import collapse_ws, detect_injection, fold
from .policy_gate import PolicyGate
from .prompts import SYSTEM_PROMPT, build_user_message, sanitize_finding
from .validator import ReplyContext, validate_reply

MAX_QUESTION_CHARS = 2000

_MSG = {
    "vi": {
        "blocked": "Yêu cầu bị chặn: trợ lý AI không có quyền SSH hay thực thi lệnh, và không thể bỏ qua phê duyệt/allowlist. "
                   "Nếu muốn thay đổi cấu hình, hãy dùng luồng Preview → Validate → Approve → Execute → Verify.",
        "no_findings": "Không có finding nào được cung cấp nên chưa đủ dữ liệu để trả lời. Hãy chạy scan hoặc chọn một finding.",
        "need_params": "Để tạo đề xuất VLAN cần đủ 3 tham số: số VLAN, tên VLAN và cổng access (ví dụ: tạo VLAN 25 tên LAB_TEST trên Gi0/2). Còn thiếu: {missing}.",
        "vlan_ok": "Đã tạo đề xuất (CHƯA thực thi): VLAN {vlan_id} tên {name} trên {interface}. "
                   "Bước tiếp theo: gửi đề xuất này tới bước Preview của backend để validate và chờ phê duyệt.",
        "vlan_rejected": "Đề xuất bị từ chối bởi chính sách lab: {errors}.",
        "not_failed": "Finding này không ở trạng thái FAIL nên không có gì cần giải thích/khắc phục.",
        "too_long": "Câu hỏi quá dài (tối đa {n} ký tự).",
        "empty": "Câu hỏi trống.",
    },
    "en": {
        "blocked": "Request blocked: the AI assistant cannot SSH or execute commands and cannot bypass approval/allowlist. "
                   "To change a configuration use Preview → Validate → Approve → Execute → Verify.",
        "no_findings": "No findings were provided, so there is not enough data to answer. Run a scan or select a finding.",
        "need_params": "A VLAN proposal needs 3 parameters: VLAN id, VLAN name and an access port (e.g. create VLAN 25 named LAB_TEST on Gi0/2). Missing: {missing}.",
        "vlan_ok": "Proposal created (NOT executed): VLAN {vlan_id} named {name} on {interface}. "
                   "Next: send it to the backend Preview step for validation and approval.",
        "vlan_rejected": "Proposal rejected by lab policy: {errors}.",
        "not_failed": "This finding is not in FAIL status; nothing to explain or fix.",
        "too_long": "Question too long (max {n} characters).",
        "empty": "Empty question.",
    },
}

_VLAN_INTENT = re.compile(r"(tao|them|cau hinh|create|add|configure|make)\b.*\bvlan\b|\bvlan\b.*(tao|create|add)", re.S)
_VLAN_ID = re.compile(r"\bvlan\s*(?:id\s*)?(\d{1,4})\b", re.I)
_VLAN_NAME = re.compile(r"(?:t[eê]n|name|named)\s+[\"']?([A-Za-z0-9_-]{1,32})", re.I)
_VLAN_IFACE = re.compile(r"\b(fa|fastethernet|gi|gigabitethernet)\s*(\d+/\d+(?:/\d+)?)", re.I)


def parse_vlan_request(message: str) -> dict:
    """Trích tham số tác vụ VLAN bằng regex (xác định, không qua LLM)."""
    if not _VLAN_INTENT.search(fold(message)):
        return {"intent": False}
    vid = _VLAN_ID.search(message)
    nm = _VLAN_NAME.search(message)
    ifc = _VLAN_IFACE.search(message)
    return {
        "intent": True,
        "vlan_id": int(vid.group(1)) if vid else None,
        "name": nm.group(1) if nm else None,
        "interface": (ifc.group(1) + ifc.group(2)) if ifc else None,
    }


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _event(name, **detail):
    return {"event": name, "ts": _now(), "detail": detail}


def _blank_reply(answer, **over):
    r = {"answer": answer, "why_it_matters": "", "evidence_used": [], "risk_level": None, "impact_of_fix": "",
         "manual_steps": [], "proposed_action": None, "confidence": "high", "insufficient_data": False,
         "injection_noticed": False}
    r.update(over)
    return r


class AssistantService:
    def __init__(self, llm, rules, policy: PolicyGate, max_retries: int = 1):
        self.llm = llm
        self.rules = {r["rule_id"]: r for r in rules}
        self.policy = policy
        self.max_retries = max_retries
        self.extra_allowed = frozenset(fold(collapse_ws(line)) for r in rules for line in r.get("remediation", []))

    # ------------------------------------------------------------ public API
    def explain_finding(self, finding: dict, language: str = "vi") -> dict:
        m = _MSG.get(language, _MSG["vi"])
        events = [_event("assistant.explain.request", rule_id=finding.get("rule_id"), device=finding.get("device_name"))]
        if finding.get("status") != "FAIL":
            return {"ok": False, "source": "gate", "error": "finding_not_failed", "message": m["not_failed"],
                    "audit_events": events}
        ctx_findings = self._context([finding])
        return self._answer_with_llm("explain_finding", language, ctx_findings, "", False, events,
                                     fallback_finding=finding)

    def chat(self, message: str, findings: list, language: str = "vi") -> dict:
        m = _MSG.get(language, _MSG["vi"])
        events = [_event("assistant.chat.request", chars=len(message or ""), n_findings=len(findings or []))]
        if not (message or "").strip():
            return {"ok": False, "source": "gate", "error": "empty", "message": m["empty"], "audit_events": events}
        if len(message) > MAX_QUESTION_CHARS:
            return {"ok": False, "source": "gate", "error": "too_long", "message": m["too_long"].format(n=MAX_QUESTION_CHARS),
                    "audit_events": events}

        # 1) Gate xác định: chặn yêu cầu vượt quyền/injection TRƯỚC khi gọi LLM
        sigs = detect_injection(message)
        if sigs:
            events.append(_event("assistant.request_blocked", signatures=sigs))
            return {"ok": False, "source": "gate", "blocked": True, "reason_codes": sigs, "message": m["blocked"],
                    "audit_events": events}

        # 2) Yêu cầu tạo VLAN -> trích tham số bằng regex, kiểm bằng policy; LLM không tham gia
        vl = parse_vlan_request(message)
        if vl["intent"]:
            return self._vlan_proposal(vl, language, events)

        # 3) Không có dữ liệu -> không gọi LLM, không bịa
        failed = [f for f in (findings or []) if f.get("status") == "FAIL"]
        if not failed:
            reply = _blank_reply(m["no_findings"], insufficient_data=True, confidence="high")
            return {"ok": True, "source": "gate", "reply": reply, "warnings": [], "audit_events": events}

        return self._answer_with_llm("answer_question", language, self._context(failed), message, False, events)

    # ------------------------------------------------------------- internals
    def _context(self, findings):
        merged = {}
        for f in findings:
            s = sanitize_finding(f)
            if s["rule_id"] in merged:
                merged[s["rule_id"]]["evidence"] += s["evidence"]
            else:
                merged[s["rule_id"]] = s
        return merged

    def _vlan_proposal(self, vl, language, events):
        m = _MSG.get(language, _MSG["vi"])
        missing = [k for k in ("vlan_id", "name", "interface") if vl.get(k) is None]
        if missing:
            reply = _blank_reply(m["need_params"].format(missing=", ".join(missing)), insufficient_data=True)
            return {"ok": True, "source": "deterministic", "reply": reply, "warnings": [], "audit_events": events}
        params = {"vlan_id": vl["vlan_id"], "name": vl["name"], "interface": vl["interface"]}
        errs = self.policy.check_vlan_params(params)
        if errs:
            events.append(_event("assistant.action_rejected", params=params, errors=errs))
            return {"ok": False, "source": "policy", "error": "policy_violation", "errors": errs,
                    "message": m["vlan_rejected"].format(errors=", ".join(errs)), "audit_events": events}
        norm = self.policy.normalize_vlan_params(params)
        reply = _blank_reply(m["vlan_ok"].format(**norm),
                             proposed_action={"action_type": "create_vlan_assign_access_port", "params": norm},
                             manual_steps=[f"vlan {norm['vlan_id']}", f"name {norm['name']}", "exit",
                                           f"interface {norm['interface']}", "switchport mode access",
                                           f"switchport access vlan {norm['vlan_id']}", "no shutdown"])
        ctx = ReplyContext({}, self.policy, self.extra_allowed, allow_action=True)
        valid, verrs = validate_reply(json.dumps(reply), ctx)
        if verrs:                                   # không bao giờ xảy ra nếu code đúng; fail-closed nếu có
            events.append(_event("assistant.internal_validation_failed", errors=verrs))
            return {"ok": False, "source": "policy", "error": "internal_validation_failed", "errors": verrs,
                    "message": "Lỗi nội bộ khi dựng đề xuất.", "audit_events": events}
        events.append(_event("assistant.action_proposed", params=norm, executed=False))
        return {"ok": True, "source": "deterministic", "reply": valid, "warnings": [], "audit_events": events}

    def _answer_with_llm(self, task, language, ctx_findings, question, allow_action, events, fallback_finding=None):
        warnings = []
        inj = {rid: f["_injection_signatures"] for rid, f in ctx_findings.items() if f["_injection_signatures"]}
        if inj:
            warnings.append("injection_suspected_in_evidence:" + ",".join(sorted(inj)))
            events.append(_event("assistant.injection_in_evidence", rule_ids=sorted(inj), signatures=inj))

        ctx = ReplyContext(ctx_findings, self.policy, self.extra_allowed, allow_action)
        feedback, attempts = None, 0
        for attempt in range(1 + self.max_retries):
            attempts += 1
            user = build_user_message(task, language, list(ctx_findings.values()), question, allow_action, feedback)
            try:
                raw = self.llm.complete(SYSTEM_PROMPT, user)
            except Exception as e:                  # timeout, HTTP lỗi, hết quota...
                warnings.append(f"llm_error:{type(e).__name__}")
                events.append(_event("assistant.llm_error", error=type(e).__name__, attempt=attempt + 1))
                break                                # lỗi hạ tầng: không retry mù, dùng fallback
            reply, errs = validate_reply(raw, ctx)
            if not errs:
                events.append(_event("assistant.reply_accepted", attempts=attempts))
                return {"ok": True, "source": "llm", "reply": reply, "warnings": warnings, "attempts": attempts,
                        "audit_events": events}
            digest = hashlib.sha256(str(raw).encode("utf-8", "replace")).hexdigest()[:16]
            events.append(_event("assistant.llm_reply_rejected", errors=errs, attempt=attempt + 1, output_sha256=digest))
            warnings.append("llm_reply_rejected:" + ";".join(errs[:5]))
            feedback = errs

        # Fallback xác định: chỉ dùng dữ liệu của rule + evidence đã có
        events.append(_event("assistant.fallback_used"))
        if fallback_finding is not None:
            f = sanitize_finding(fallback_finding)
            reply = build_fallback_reply(f, self.rules.get(f["rule_id"], {}), language)
        else:
            reply = _blank_reply(
                "Hiện không thể tạo câu trả lời AI đã được kiểm chứng. Vui lòng xem chi tiết từng finding (bằng chứng và hướng khắc phục của rule).",
                insufficient_data=True, confidence="low")
        return {"ok": True, "source": "fallback", "reply": reply, "warnings": warnings, "attempts": attempts,
                "audit_events": events}
