# scripts/test_week6.py  --  Tuần 6: template, validator, verifier, evidence, rollback
import json
import os
import tempfile

from tests import fakes
from app.devices.network_adapter import NetworkAdapter
from app.remediation.syntax_validator import parse_ios_version, validate_ios_syntax
from app.remediation.task_template import (TaskValidationError, build_rollback_commands, build_vlan_task, get_vlan_template,
                           load_policy, validate_vlan_params)
from tests.testing_utils import run_tests
from app.remediation.verifier_and_evidence import (generate_task_evidence, parse_show_vlan_brief, parse_switchport, save_evidence,
                                   verify_vlan, verify_vlan_outputs, vlan_exists)

POLICY = load_policy()
DEV = {"id": "dev_switch_01", "name": "Switch-LAB", "ip": "172.16.3.122", "device_type": "cisco_ios", "role": "switch"}
EXPECT = {"vlan_id": 20, "vlan_name": "IT_DEPT", "interface": "GigabitEthernet0/1"}


def _rejected(*args):
    try:
        validate_vlan_params(*args, policy=POLICY)
    except TaskValidationError as e:
        return e.errors
    return None


# ---------------- template ----------------
def test_template_output_and_normalization():
    cmds = get_vlan_template("20", "IT_DEPT", "Gi0/1", POLICY)
    assert cmds == ["vlan 20", " name IT_DEPT", "exit", "interface GigabitEthernet0/1",
                    " switchport mode access", " switchport access vlan 20", " no shutdown"]
    assert not any(c.strip() in ("configure terminal", "end", "write memory") for c in cmds)


def test_template_blocks_dangerous_parameters():
    cases = [(9999, "A", "Gi0/1"), (0, "A", "Gi0/1"), (1, "A", "Gi0/1"), (1003, "A", "Gi0/1"), (30, "A", "Gi0/1"),
             ("20; reload", "A", "Gi0/1"), (True, "A", "Gi0/1"), (20.5, "A", "Gi0/1"),
             (20, "A\nreload", "Gi0/1"), (20, "A B", "Gi0/1"), (20, "", "Gi0/1"), (20, "X" * 33, "Gi0/1"),
             (20, "A", "Gi0/24"), (20, "A", "Gi0/1\nreload"), (20, "A", "Gi0/1; reload"), (20, "A", "Vlan1"),
             (20, "A", "TenGigabitEthernet1/1/1"), (20, "A", None)]
    for case in cases:
        assert _rejected(*case), f"Lẽ ra phải chặn: {case!r}"


def test_template_respects_protected_interfaces():
    pol = dict(POLICY, protected_interfaces=["GigabitEthernet0/1"])
    try:
        validate_vlan_params(20, "A", "Gi0/1", pol)
        assert False
    except TaskValidationError as e:
        assert "bảo vệ" in e.errors[0]


def test_template_reports_all_errors_at_once():
    errs = _rejected(9999, "bad name", "Gi0/24")
    assert len(errs) == 3


def test_build_vlan_task_package():
    t = build_vlan_task(20, "IT_DEPT", "Gi0/1", POLICY)
    assert t["action_type"] == "create_vlan_assign_access_port" and t["params"]["interface_name"] == "GigabitEthernet0/1"
    assert t["verify_commands"] == ["show vlan brief", "show interfaces GigabitEthernet0/1 switchport"]
    assert t["save_after_verify"] is True and t["pre_check_commands"][0] == "show vlan brief"


# ---------------- validator ----------------
def test_validator_accepts_template_output():
    cmds = get_vlan_template(20, "IT_DEPT", "Gi0/1", POLICY)
    r = validate_ios_syntax(cmds, "15.2", model="Cisco Catalyst 2960", device_role="switch", policy=POLICY)
    assert r["status"] == "VALID", r


def test_validator_version_parsing_is_correct():
    assert parse_ios_version("15.2(4)E7") == (15, 2) and parse_ios_version("12.2(55)SE") == (12, 2)
    assert parse_ios_version("16.9.4") == (16, 9)
    for v in ("12.2", "12.2(55)SE", "15.0", "15.2(4)E7"):
        r = validate_ios_syntax(["vlan database"], v)
        assert r["status"] == "INVALID" and "lỗi thời" in r["errors"][0], (v, r)
    assert validate_ios_syntax(["vlan 20"], "abc")["status"] == "INVALID"


def test_validator_requires_mode_access_in_same_interface():
    r = validate_ios_syntax(["interface Gi0/1", "switchport access vlan 20"], "15.2", policy=POLICY)
    assert r["status"] == "INVALID" and any("switchport mode access" in e for e in r["errors"])
    two = ["interface Gi0/1", "switchport mode access", "interface Gi0/2", "switchport access vlan 20"]
    assert validate_ios_syntax(two, "15.2", policy=POLICY)["status"] == "INVALID"   # mode access của interface KHÁC không tính


def test_validator_allowlist_blocks_everything_else():
    for bad in ["reload", "write erase", "copy run tftp", "username x privilege 15 secret y", "shutdown",
                "no vlan 1", "interface Vlan1", "line vty 0 4", "enable secret x", "vlan 20 ; reload", "show run"]:
        assert validate_ios_syntax([bad], "15.2", policy=POLICY)["status"] == "INVALID", bad
    assert validate_ios_syntax(["vlan 20\nreload"], "15.2")["status"] == "INVALID"
    assert validate_ios_syntax(["vlan 20", "name ?"], "15.2")["status"] == "INVALID"
    assert validate_ios_syntax([], "15.2")["status"] == "INVALID"


def test_validator_applies_model_role_and_policy():
    sw = ["interface Gi0/1", "switchport mode access"]
    assert any("router" in e for e in validate_ios_syntax(sw, "15.2", device_role="router")["errors"])
    assert validate_ios_syntax(["interface Gi0/24"], "15.2", policy=POLICY)["status"] == "INVALID"
    assert validate_ios_syntax(["vlan 99"], "15.2", policy=POLICY)["status"] == "INVALID"
    r = validate_ios_syntax(["vlan 20"], "15.2", model="Cisco XYZ-9000")
    assert r["status"] == "VALID" and any("hồ sơ" in w for w in r["warnings"])
    assert validate_ios_syntax(["interface Gi0/1"], "15.2", model="WS-C2960-24TT-L")["status"] == "VALID"


def test_validator_warns_when_vlan_not_declared():
    r = validate_ios_syntax(["interface Gi0/1", "switchport mode access", "switchport access vlan 21"], "15.2", policy=POLICY)
    assert r["status"] == "VALID" and r["warnings"]


# ---------------- parsers ----------------
def test_parse_show_vlan_brief_with_wrapped_ports():
    v = parse_show_vlan_brief(fakes.VLAN_BRIEF_BEFORE)
    assert v[1]["ports"] == ["FastEthernet0/2", "FastEthernet0/3", "FastEthernet0/4", "FastEthernet0/5",
                             "FastEthernet0/6", "GigabitEthernet0/1", "GigabitEthernet0/2"]
    assert 20 not in v and v[1002]["status"] == "act/unsup" and v[1002]["ports"] == []
    assert v and vlan_exists(fakes.VLAN_BRIEF_AFTER, 20) and not vlan_exists(fakes.VLAN_BRIEF_BEFORE, 20)
    assert parse_show_vlan_brief("") == {}


def test_parse_switchport():
    sp = parse_switchport(fakes.SWITCHPORT_AFTER)
    assert sp["name"] == "Gi0/1" and sp["admin_mode"] == "static access" and sp["access_vlan"] == 20


# ---------------- verifier (không còn luôn PASS) ----------------
def _verify(vlan_brief, switchport, **over):
    e = dict(EXPECT, **over)
    return verify_vlan_outputs(vlan_brief, switchport, e["vlan_id"], e["vlan_name"], e["interface"])


def test_verifier_pass_on_correct_state():
    r = _verify(fakes.VLAN_BRIEF_AFTER, fakes.SWITCHPORT_AFTER)
    assert r["verification_status"] == "PASS" and len(r["checks"]) == 6 and all(c["passed"] for c in r["checks"])
    assert r["parsed_result"]["assigned_ports"] == ["GigabitEthernet0/1"]


def test_verifier_fails_when_change_not_applied():
    r = _verify(fakes.VLAN_BRIEF_BEFORE, fakes.SWITCHPORT_BEFORE)
    assert r["verification_status"] == "FAIL"
    failed = {c["name"] for c in r["checks"] if not c["passed"]}
    assert {"vlan_exists", "access_vlan", "admin_mode_access"} <= failed


def test_verifier_detects_each_kind_of_mismatch():
    assert _verify(fakes.VLAN_BRIEF_AFTER, fakes.SWITCHPORT_AFTER, vlan_name="OTHER")["verification_status"] == "FAIL"
    assert _verify(fakes.VLAN_BRIEF_AFTER, fakes.SWITCHPORT_AFTER, interface="Gi0/2")["verification_status"] == "FAIL"
    assert _verify(fakes.VLAN_BRIEF_AFTER, fakes.SWITCHPORT_AFTER, vlan_id=21)["verification_status"] == "FAIL"
    wrong_vlan = fakes.SWITCHPORT_AFTER.replace("Access Mode VLAN: 20", "Access Mode VLAN: 30")
    assert _verify(fakes.VLAN_BRIEF_AFTER, wrong_vlan)["verification_status"] == "FAIL"
    inactive = fakes.VLAN_BRIEF_AFTER.replace("IT_DEPT                          active", "IT_DEPT                          suspended")
    assert _verify(inactive, fakes.SWITCHPORT_AFTER)["verification_status"] == "FAIL"


def test_verifier_error_on_empty_or_garbage_output():
    for vb, sp in [("", ""), (fakes.VLAN_BRIEF_AFTER, ""), ("% Invalid input detected at '^' marker.", fakes.SWITCHPORT_AFTER),
                   (fakes.VLAN_BRIEF_AFTER, "% Invalid input detected at '^' marker.")]:
        assert _verify(vb, sp)["verification_status"] == "ERROR"


# ---------------- evidence ----------------
def test_evidence_status_is_derived_not_hardcoded():
    ok = generate_task_evidence("T1", "Switch-LAB", "WS-C2960", "15.0", ["vlan 20"], device_id="dev_switch_01",
                                execution_output="", verify_outputs={"vlan_brief": fakes.VLAN_BRIEF_AFTER, "switchport": fakes.SWITCHPORT_AFTER},
                                expected=EXPECT)
    assert ok["execution_payload"]["status"] == "SUCCESS" and ok["verification_steps"]["verification_status"] == "PASS"
    assert ok["overall_status"] == "PASS"
    failed_exec = generate_task_evidence("T2", "S", "m", "15.0", ["foo"], execution_output="% Invalid input detected at '^' marker.")
    assert failed_exec["execution_payload"]["status"] == "FAILED" and failed_exec["overall_status"] == "FAILED"
    assert failed_exec["verification_steps"]["verification_status"] == "NOT_RUN"
    not_run = generate_task_evidence("T3", "S", "m", "15.0", ["vlan 20"])
    assert not_run["overall_status"] == "NOT_EXECUTED"
    bad_verify = generate_task_evidence("T4", "S", "m", "15.0", ["vlan 20"], execution_output="",
                                        verify_outputs={"vlan_brief": fakes.VLAN_BRIEF_BEFORE, "switchport": fakes.SWITCHPORT_BEFORE}, expected=EXPECT)
    assert bad_verify["overall_status"] == "FAIL"


def test_evidence_sanitizes_outputs_and_hashes_commands():
    ev = generate_task_evidence("T5", "S", "m", "15.0", ["vlan 20"], execution_output="enable secret 5 $1$x$LEAKME\n")
    assert "LEAKME" not in json.dumps(ev) and len(ev["execution_payload"]["commands_sha256"]) == 64


def test_evidence_saved_as_valid_json():
    ev = generate_task_evidence("TASK/VLAN:001", "Switch-LAB", "WS-C2960", "15.0", ["vlan 20"], execution_output="")
    with tempfile.TemporaryDirectory() as d:
        path = save_evidence(ev, d)
        assert os.path.basename(path) == "evidence_TASK_VLAN_001.json"
        assert json.load(open(path, encoding="utf-8"))["task_metadata"]["task_id"] == "TASK/VLAN:001"


# ---------------- rollback ----------------
def test_rollback_restores_previous_interface_state():
    params = {"vlan_id": 20, "vlan_name": "IT_DEPT", "interface_name": "GigabitEthernet0/1"}
    rb = build_rollback_commands(params, fakes.IF_RUNNING_BEFORE, vlan_existed_before=False)
    assert rb == ["default interface GigabitEthernet0/1", "interface GigabitEthernet0/1",
                  " switchport mode dynamic auto", " description lab-port", "exit", "no vlan 20"]
    assert validate_ios_syntax(rb, "15.0", policy=POLICY, mode="rollback")["status"] == "VALID"
    keep = build_rollback_commands(params, fakes.IF_RUNNING_BEFORE, vlan_existed_before=True)
    assert "no vlan 20" not in keep


def test_rollback_refuses_without_pre_change_config():
    params = {"vlan_id": 20, "vlan_name": "IT_DEPT", "interface_name": "GigabitEthernet0/1"}
    for pre in ("", None, "interface GigabitEthernet0/2\n switchport mode access\n"):
        try:
            build_rollback_commands(params, pre, False)
            assert False
        except TaskValidationError:
            pass


def test_rollback_mode_still_blocks_dangerous_lines():
    bad = ["default interface GigabitEthernet0/1", "interface GigabitEthernet0/1", " reload"]
    assert validate_ios_syntax(bad, "15.0", policy=POLICY, mode="rollback")["status"] == "INVALID"
    assert validate_ios_syntax(["default interface GigabitEthernet0/24"], "15.0", policy=POLICY, mode="rollback")["status"] == "INVALID"


# ---------------- luồng đầy đủ trên thiết bị giả ----------------
def test_end_to_end_workflow_on_fake_switch():
    on_config = {"show vlan brief": fakes.VLAN_BRIEF_AFTER,
                 "show interfaces GigabitEthernet0/1 switchport": fakes.SWITCHPORT_AFTER}
    f = fakes.make_factory(fakes.standard_outputs(), on_config=on_config)
    with NetworkAdapter(DEV, username="u", password="p", connection_factory=f) as ad:
        info = ad.get_device_info()
        task = build_vlan_task(20, "IT_DEPT", "Gi0/1", POLICY)                                     # PREVIEW
        v = validate_ios_syntax(task["config_commands"], info["ios_version"], model=info["model"], device_role="switch", policy=POLICY)
        assert v["status"] == "VALID", v                                                           # VALIDATE
        pre_vlan = ad.run_show("show vlan brief")
        pre_if = ad.run_show("show running-config interface GigabitEthernet0/1")
        rollback = build_rollback_commands(task["params"], pre_if, vlan_exists(pre_vlan, 20))      # chuẩn bị rollback
        res = ad.apply_config(task["config_commands"])                                             # EXECUTE (sau khi approve)
        assert res["ok"] is True
        result = verify_vlan(ad.run_show, 20, "IT_DEPT", "Gi0/1")                                  # VERIFY
        assert result["verification_status"] == "PASS"
        ev = generate_task_evidence("TASK-VLAN-001", DEV["name"], info["model"], info["ios_version"], task["config_commands"],
                                    device_id=DEV["id"], execution_output=res["output"], verify_outputs=result["raw_outputs"],
                                    expected=EXPECT, rollback_commands=rollback)
        assert ev["overall_status"] == "PASS"
        ad.save_config()
    conn = f.holder["conn"]
    assert conn.sent_config == [task["config_commands"]] and conn.saved is True and conn.disconnected is True


def test_end_to_end_detects_failed_change():
    f = fakes.make_factory(fakes.standard_outputs())     # thiết bị KHÔNG đổi trạng thái sau khi apply
    with NetworkAdapter(DEV, username="u", password="p", connection_factory=f) as ad:
        ad.apply_config(get_vlan_template(20, "IT_DEPT", "Gi0/1", POLICY))
        assert verify_vlan(ad.run_show, 20, "IT_DEPT", "Gi0/1")["verification_status"] == "FAIL"


def test_adapter_flags_ios_errors_on_apply():
    f = fakes.make_factory(fakes.standard_outputs(), config_output="vlan 20\n% Invalid input detected at '^' marker.\n")
    with NetworkAdapter(DEV, username="u", password="p", connection_factory=f) as ad:
        res = ad.apply_config(["vlan 20"])
        assert res["ok"] is False and res["errors"]
        for bad in ([], [" "], ["vlan 20\nreload"], ["name ?"]):
            try:
                ad.apply_config(bad)
                assert False, bad
            except Exception as e:  # AdapterError
                assert getattr(e, "error_type", None) == "COMMAND"


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_tests(globals(), "TUẦN 6 - template / validator / verifier / rollback") else 1)
