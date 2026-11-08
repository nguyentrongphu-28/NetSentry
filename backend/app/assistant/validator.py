"""Validator cho đầu ra của LLM. Mọi thứ LLM trả về đều là dữ liệu không tin cậy."""
import json
import re
from dataclasses import dataclass, field

from .guards import (URL_OR_RENDER, check_command_line, collapse_ws, find_dangerous_in_prose, find_secrets)
from .policy_gate import PolicyGate

REPLY_KEYS = {"answer", "why_it_matters", "evidence_used", "risk_level", "impact_of_fix", "manual_steps",
              "proposed_action", "confidence", "insufficient_data", "injection_noticed"}
SEVERITIES = {"LOW", "MEDIUM", "HIGH"}
CONFIDENCE = {"low", "medium", "high"}
ACTION_TYPES = {"create_vlan_assign_access_port"}       # allowlist action; mở rộng khi A thêm template mới
ACTION_PARAM_KEYS = {"vlan_id", "name", "interface"}
LIMITS = {"answer": 1500, "why_it_matters": 1000, "impact_of_fix": 800, "quote": 300, "step": 200,
          "steps": 20, "evidence": 10}


@dataclass
class ReplyContext:
    findings: dict                                  # rule_id -> finding (đã làm sạch)
    policy: PolicyGate
    extra_allowed: frozenset = frozenset()          # các dòng remediation đã được duyệt trong rules.json
    allow_action: bool = False                      # người dùng có thật sự yêu cầu tạo VLAN không


def parse_json_text(raw):
    """Chấp nhận đúng 1 object JSON, có thể bọc trong ```json ... ```. Không 'vớt' JSON từ văn bản tự do."""
    if not isinstance(raw, str):
        return None, ["not_text"]
    s = raw.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, re.S | re.I)
    if m:
        s = m.group(1)
    try:
        obj = json.loads(s)
    except ValueError:
        return None, ["not_json"]
    if not isinstance(obj, dict):
        return None, ["json_not_object"]
    return obj, []


def _text_checks(name, value, limit, errs, min_len=0):
    if not isinstance(value, str):
        errs.append(f"{name}:not_string")
        return
    if len(value) > limit or len(value) < min_len:
        errs.append(f"{name}:bad_length")
    if URL_OR_RENDER.search(value):
        errs.append(f"{name}:url_or_markup")
    if find_secrets(value, prose=True):
        errs.append(f"{name}:contains_secret")
    if name != "quote" and find_dangerous_in_prose(value):
        errs.append(f"{name}:dangerous_command")


def validate_reply(raw, ctx: ReplyContext):
    """-> (reply_dict | None, errors[list of codes]). Mã lỗi không chứa nội dung của LLM (an toàn để log/feedback)."""
    obj, errs = parse_json_text(raw)
    if errs:
        return None, errs

    keys = set(obj)
    if keys != REPLY_KEYS:
        if REPLY_KEYS - keys:
            errs.append("missing_keys:" + ",".join(sorted(REPLY_KEYS - keys)))
        if keys - REPLY_KEYS:
            errs.append("extra_keys:" + ",".join(sorted(keys - REPLY_KEYS)))
        return None, errs

    _text_checks("answer", obj["answer"], LIMITS["answer"], errs, min_len=1)
    _text_checks("why_it_matters", obj["why_it_matters"], LIMITS["why_it_matters"], errs)
    _text_checks("impact_of_fix", obj["impact_of_fix"], LIMITS["impact_of_fix"], errs)

    if not isinstance(obj["insufficient_data"], bool):
        errs.append("insufficient_data:not_bool")
    if not isinstance(obj["injection_noticed"], bool):
        errs.append("injection_noticed:not_bool")
    if obj["confidence"] not in CONFIDENCE:
        errs.append("confidence:bad_enum")

    # --- risk_level: AI không được hạ/nâng mức độ do rule engine đã quyết định
    allowed_sev = {f.get("severity") for f in ctx.findings.values()}
    rl = obj["risk_level"]
    if rl is not None and (rl not in SEVERITIES or rl not in allowed_sev):
        errs.append("risk_level:mismatch_with_findings")

    # --- evidence phải có thật trong dữ liệu đã cung cấp (chống bịa)
    ev = obj["evidence_used"]
    if not isinstance(ev, list) or len(ev) > LIMITS["evidence"]:
        errs.append("evidence_used:bad_list")
        ev = []
    for item in ev:
        if not (isinstance(item, dict) and set(item) == {"rule_id", "quote"}):
            errs.append("evidence_used:bad_item")
            continue
        f = ctx.findings.get(item["rule_id"])
        if f is None:
            errs.append("evidence_used:unknown_rule_id")
            continue
        _text_checks("quote", item["quote"], LIMITS["quote"], errs, min_len=1)
        hay = collapse_ws(" ".join(str(x) for x in f.get("evidence", []))).lower()
        if isinstance(item["quote"], str) and collapse_ws(item["quote"]).lower() not in hay:
            errs.append("evidence_used:quote_not_in_evidence")
    if (ctx.findings and obj["insufficient_data"] is False and not ev and obj["proposed_action"] is None):
        errs.append("evidence_used:required_when_data_available")

    # --- manual_steps: chỉ lệnh trong allowlist, chỉ để HIỂN THỊ (không bao giờ tự thực thi)
    steps = obj["manual_steps"]
    if not isinstance(steps, list) or len(steps) > LIMITS["steps"]:
        errs.append("manual_steps:bad_list")
        steps = []
    for line in steps:
        if not isinstance(line, str):
            errs.append("manual_steps:not_string")
            continue
        ok, reason = check_command_line(line, ctx.extra_allowed)
        if not ok:
            errs.append("manual_steps:" + reason)

    # --- proposed_action: duy nhất 1 loại, chỉ khi người dùng yêu cầu, và phải qua policy
    act = obj["proposed_action"]
    if act is not None:
        if not ctx.allow_action:
            errs.append("proposed_action:not_requested")
        elif obj["insufficient_data"] is True:
            errs.append("proposed_action:with_insufficient_data")
        elif not (isinstance(act, dict) and set(act) == {"action_type", "params"}):
            errs.append("proposed_action:bad_shape")
        elif act["action_type"] not in ACTION_TYPES:
            errs.append("proposed_action:type_not_allowed")
        elif not (isinstance(act["params"], dict) and set(act["params"]) == ACTION_PARAM_KEYS):
            errs.append("proposed_action:bad_params_shape")
        else:
            errs += ["proposed_action:" + e for e in ctx.policy.check_vlan_params(act["params"])]

    if errs:
        return None, errs
    if act is not None:
        obj["proposed_action"] = {"action_type": act["action_type"],
                                  "params": ctx.policy.normalize_vlan_params(act["params"]),
                                  "requires_approval": True}
    return obj, []
