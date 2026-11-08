# scripts/test_week4.py  --  Tuần 4: rule audit, evidence, đúng/sai có kiểm soát
import json

from app.core.paths import SAMPLE_DIR
from app.audit.rule_engine import evaluate_config, load_rules, summarize, validate_rules
from app.devices.sanitizer import sanitize_config
from tests.testing_utils import run_tests

RULES = load_rules()
GROUND_TRUTH = json.load(open(SAMPLE_DIR / "expected_results.json", encoding="utf-8"))
FINDING_KEYS = {"rule_id", "device_id", "title", "severity", "status", "evidence", "rationale", "remediation", "checked_at"}


def _eval(name, role):
    return {f["rule_id"]: f for f in evaluate_config((SAMPLE_DIR / name).read_text(encoding="utf-8"), {"id": "t", "name": name, "role": role}, RULES)}


def _eval_text(text, role="switch"):
    return {f["rule_id"]: f for f in evaluate_config(text, {"role": role}, RULES)}


def test_rules_file_is_valid_and_sufficient():
    assert validate_rules(RULES) == []
    assert len(RULES) >= 5
    assert all(r["remediation"] for r in RULES)


def test_findings_follow_team_schema():
    for f in evaluate_config((SAMPLE_DIR / "switch_bad.cfg").read_text(), {"id": "dev_switch_01", "name": "S", "role": "switch"}, RULES):
        assert FINDING_KEYS <= set(f), f["rule_id"]
        assert f["status"] in ("PASS", "FAIL", "NOT_APPLICABLE", "ERROR")
        assert f["severity"] in ("HIGH", "MEDIUM", "LOW") and f["checked_at"].endswith("+00:00")


def test_ground_truth_every_rule_every_config():
    mismatches = []
    for name, expected in GROUND_TRUTH.items():
        if name.startswith("_"):
            continue
        got = _eval(name, expected["role"])
        for rid, want in expected.items():
            if rid != "role" and got[rid]["status"] != want:
                mismatches.append((name, rid, want, got[rid]["status"], got[rid]["evidence"]))
    assert not mismatches, mismatches


def test_precision_recall_on_controlled_set():
    tp = fp = fn = tn = 0
    for name, expected in GROUND_TRUTH.items():
        if name.startswith("_"):
            continue
        got = _eval(name, expected["role"])
        for rid, want in expected.items():
            if rid == "role":
                continue
            pred = got[rid]["status"] == "FAIL"
            if want == "FAIL":
                tp, fn = tp + pred, fn + (not pred)
            else:
                fp, tn = fp + pred, tn + (not pred)
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    print(f"      (bộ mẫu có kiểm soát: TP={tp} FP={fp} FN={fn} TN={tn} | precision={precision:.2f} recall={recall:.2f})")
    assert precision == 1.0 and recall == 1.0


def test_every_failure_carries_checkable_evidence():
    for name in ("switch_bad.cfg", "switch_edge_cases.cfg", "router_bad.cfg"):
        for rid, f in _eval(name, "switch" if name.startswith("switch") else "router").items():
            if f["status"] == "FAIL":
                assert f["evidence"] and all(isinstance(e, str) and e for e in f["evidence"]), (name, rid)


def test_edge_exec_timeout_zero_zero_is_violation():
    cfg = "hostname X\nline vty 0 4\n exec-timeout 0 0\n"
    assert _eval_text(cfg)["SEC-003"]["status"] == "FAIL"
    assert _eval_text("hostname X\nline vty 0 4\n exec-timeout 10 0\n")["SEC-003"]["status"] == "PASS"
    assert _eval_text("hostname X\nline vty 0 4\n exec-timeout 0 30\n")["SEC-003"]["status"] == "PASS"


def test_edge_telnet_and_ssh_together_fails():
    assert _eval_text("hostname X\nline vty 0 4\n transport input telnet ssh\n")["SEC-002"]["status"] == "FAIL"


def test_edge_banner_body_is_not_config():
    cfg = "hostname X\nbanner motd ^C\nip http server\nno ip source-route\n^C\n"
    r = _eval_text(cfg)
    assert r["SEC-006"]["status"] == "PASS" and r["SEC-007"]["status"] == "FAIL" and r["SEC-004"]["status"] == "PASS"
    one_line = _eval_text("hostname X\nbanner motd ^Chello^C\nip http server\n")
    assert one_line["SEC-006"]["status"] == "FAIL"      # banner 1 dòng đã đóng -> dòng sau là cấu hình thật


def test_edge_proxy_arp_per_interface_and_not_applicable():
    two = "hostname X\ninterface Vlan10\n ip address 10.0.0.1 255.255.255.0\n no ip proxy-arp\ninterface Vlan20\n ip address 10.0.1.1 255.255.255.0\n"
    assert _eval_text(two)["SEC-009"]["status"] == "FAIL"
    l2_only = "hostname X\ninterface Vlan1\n no ip address\n shutdown\ninterface Loopback0\n ip address 10.9.9.9 255.255.255.255\n"
    assert _eval_text(l2_only)["SEC-009"]["status"] == "NOT_APPLICABLE"


def test_edge_missing_blocks_is_not_applicable_not_pass():
    r = _eval_text("hostname X\nservice password-encryption\n")
    assert r["SEC-002"]["status"] == "NOT_APPLICABLE" and r["SEC-001"]["status"] == "PASS"


def test_edge_domain_lookup_both_spellings():
    assert _eval_text("hostname X\nno ip domain-lookup\n")["SEC-008"]["status"] == "PASS"
    assert _eval_text("hostname X\nno ip domain lookup\n")["SEC-008"]["status"] == "PASS"
    assert _eval_text("hostname X\nip domain-name lab.local\n")["SEC-008"]["status"] == "FAIL"


def test_edge_enable_password_alone_or_with_secret_fails():
    assert _eval_text("hostname X\nenable password 7 <REDACTED>\n")["SEC-005"]["status"] == "FAIL"
    assert _eval_text("hostname X\nenable secret 5 <REDACTED>\nenable password 7 <REDACTED>\n")["SEC-005"]["status"] == "FAIL"
    assert _eval_text("hostname X\nenable secret 5 <REDACTED>\n")["SEC-005"]["status"] == "PASS"


def test_role_filter_marks_not_applicable():
    only_router = [dict(RULES[0], applies_to={"roles": ["router"]})]
    f = evaluate_config("hostname X\n", {"role": "switch"}, only_router)[0]
    assert f["status"] == "NOT_APPLICABLE"
    assert evaluate_config("hostname X\n", {"role": "router"}, only_router)[0]["status"] == "FAIL"


def test_rules_still_work_after_sanitizing_raw_config():
    raw = ("hostname X\nenable secret 5 $1$mK1q$FAKE\nsnmp-server community public RO\n"
           "snmp-server community Str0ngOne RW\nline vty 0 4\n password 7 0822455D0A16\n transport input ssh\n")
    r = _eval_text(sanitize_config(raw))
    assert r["SEC-005"]["status"] == "PASS"
    assert r["SEC-012"]["status"] == "FAIL" and "public" in " ".join(r["SEC-012"]["evidence"])
    assert "Str0ngOne" not in " ".join(" ".join(f["evidence"]) for f in r.values())


def test_summary_counts():
    s = summarize(evaluate_config((SAMPLE_DIR / "switch_bad.cfg").read_text(), {"role": "switch"}, RULES))
    assert s["fail"] == 13 and s["pass"] == 0 and sum(s["fail_by_severity"].values()) == 13


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_tests(globals(), "TUẦN 4 - rule audit & evidence") else 1)
