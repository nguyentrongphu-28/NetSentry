"""Test tích hợp: code của A (rule_engine, task_template, syntax_validator) <-> AI assistant (tuần 7).

Tuần 7 ban đầu chỉ được test với finding dựng tay; file này chạy với finding THẬT do evaluate_config() sinh ra
và kiểm tra hai phía không lệch nhau (tên action, chính sách VLAN/port, dòng remediation).
Chạy: python scripts/run_all_tests.py
"""
import itertools
import json
import os
import sys
import unittest

BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND)

from app.assistant import AssistantService, MockLLM, PolicyGate                       # noqa: E402
from app.assistant.prompts import sanitize_finding                                    # noqa: E402
from app.assistant.validator import ACTION_TYPES, ReplyContext, validate_reply        # noqa: E402
from app.audit.rule_engine import evaluate_config, load_rules                         # noqa: E402
from app.core.paths import DATA_DIR, SAMPLE_DIR                                       # noqa: E402
from app.remediation.syntax_validator import validate_ios_syntax                      # noqa: E402
from app.remediation.task_template import (ACTION_TYPE, TaskValidationError, build_vlan_task,   # noqa: E402
                                           validate_vlan_params)

RULES = load_rules()
POLICY = json.load(open(DATA_DIR / "lab_policy.json", encoding="utf-8"))
SAMPLES = [("switch_bad.cfg", "switch"), ("router_bad.cfg", "router"), ("switch_edge_cases.cfg", "switch")]


def real_fail_findings():
    out = []
    for cfg, role in SAMPLES:
        text = (SAMPLE_DIR / cfg).read_text(encoding="utf-8")
        out += [f for f in evaluate_config(text, {"id": "dev_" + role, "name": cfg, "role": role}, RULES) if f["status"] == "FAIL"]
    return out


class _Down:
    def complete(self, system, user):
        raise TimeoutError("llm down")


def llm_reply_for(f):
    rule = next(r for r in RULES if r["rule_id"] == f["rule_id"])
    return json.dumps({"answer": "Phát hiện vi phạm theo bằng chứng.", "why_it_matters": rule["description"],
                       "evidence_used": [{"rule_id": f["rule_id"], "quote": f["evidence"][0]}], "risk_level": f["severity"],
                       "impact_of_fix": "Lưu cấu hình trước khi áp dụng.", "manual_steps": list(rule["remediation"]),
                       "proposed_action": None, "confidence": "high", "insufficient_data": False,
                       "injection_noticed": False}, ensure_ascii=False)


class IntegrationAWeek7(unittest.TestCase):
    def test_int_findings_schema_matches_assistant_input(self):
        fs = real_fail_findings()
        self.assertGreaterEqual(len(fs), 20)
        for f in fs:
            self.assertIsInstance(f["evidence"], list)
            self.assertTrue(all(isinstance(x, str) for x in f["evidence"]), f["rule_id"])
            self.assertTrue(f["evidence"], f["rule_id"])

    def test_int_real_finding_accepted_on_llm_path(self):
        for f in real_fail_findings():
            r = AssistantService(MockLLM(llm_reply_for(f)), RULES, PolicyGate(POLICY)).explain_finding(f)
            self.assertEqual(r["source"], "llm", (f["rule_id"], r["warnings"]))

    def test_int_fallback_keeps_every_remediation_line_and_is_valid(self):
        for f in real_fail_findings():
            svc = AssistantService(_Down(), RULES, PolicyGate(POLICY))
            r = svc.explain_finding(f)
            self.assertEqual(r["source"], "fallback")
            rule = next(x for x in RULES if x["rule_id"] == f["rule_id"])
            self.assertEqual(len(r["reply"]["manual_steps"]), len(rule["remediation"]), f["rule_id"])
            ctx = ReplyContext({f["rule_id"]: sanitize_finding(f)}, PolicyGate(POLICY), svc.extra_allowed)
            _, errs = validate_reply(json.dumps(r["reply"], ensure_ascii=False), ctx)
            self.assertEqual(errs, [], f["rule_id"])

    def test_int_action_type_matches_task_template(self):
        self.assertEqual(ACTION_TYPES, {ACTION_TYPE})

    def test_int_policy_gate_agrees_with_task_template(self):
        gate = PolicyGate(POLICY)
        vids = [0, 1, 19, 20, 25, 29, 30, 1002, 4094, 4095, -1]
        names = ["LAB_TEST", "a b", "x;reload", "", "A" * 32, "A" * 33, "LAB\n", "tên"]
        ifs = ["Gi0/1", "gi0/2", "GigabitEthernet0/1", "Fa0/3", "Gi0/48", "Te1/0/1", "Po1", "Vlan1", "Gi0/1.10",
               "Loopback0", "Gi0/1\n", "Gi0/1\x00"]
        for v, n, i in itertools.product(vids, names, ifs):
            a = not gate.check_vlan_params({"vlan_id": v, "name": n, "interface": i})
            try:
                validate_vlan_params(v, n, i, POLICY)
                b = True
            except TaskValidationError:
                b = False
            self.assertEqual(a, b, (v, n, i))

    def test_int_ai_proposal_passes_a_preview_and_validate(self):
        svc = AssistantService(MockLLM(), RULES, PolicyGate(POLICY))
        r = svc.chat("tạo VLAN 25 tên LAB_TEST trên Gi0/2", [])
        act = r["reply"]["proposed_action"]
        self.assertEqual(act["action_type"], ACTION_TYPE)
        p = act["params"]
        # B ánh xạ khóa: name -> vlan_name, interface -> interface_name
        task = build_vlan_task(p["vlan_id"], p["name"], p["interface"], POLICY)
        self.assertEqual(task["action_type"], act["action_type"])
        v = validate_ios_syntax(task["config_commands"], "15.2", model="Cisco Catalyst 2960", device_role="switch", policy=POLICY)
        self.assertNotEqual(v["status"], "INVALID", v)


if __name__ == "__main__":
    unittest.main(verbosity=2)
