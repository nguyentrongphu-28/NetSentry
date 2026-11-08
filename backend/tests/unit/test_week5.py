# scripts/test_week5.py  --  Tuần 5: baseline, diff, drift giữa các lần snapshot
import os
import tempfile

from app.snapshots.baseline import compare_to_baseline, diff_configs, load_baseline
from app.core.paths import SAMPLE_DIR
from app.audit.rule_engine import load_rules
from app.devices.snapshot_collector import list_snapshots, load_snapshot_text, save_snapshot
from tests.testing_utils import run_tests

RULES = load_rules()
GOOD = (SAMPLE_DIR / "switch_good.cfg").read_text(encoding="utf-8")
DEV = {"id": "dev_switch_01", "name": "Switch-LAB", "ip": "172.16.3.122", "device_type": "cisco_ios", "role": "switch"}


def _read(n):
    return (SAMPLE_DIR / n).read_text(encoding="utf-8")


# ---------------- baseline ----------------
def test_good_configs_comply_with_their_baseline():
    assert compare_to_baseline(_read("switch_good.cfg"), load_baseline("switch"))["compliant"] is True
    assert compare_to_baseline(_read("router_good.cfg"), load_baseline("router"))["compliant"] is True


def test_bad_configs_report_specific_drifts():
    r = compare_to_baseline(_read("switch_bad.cfg"), load_baseline("switch"))
    assert r["compliant"] is False
    pairs = {(d["item_id"], d["type"]) for d in r["drifts"]}
    assert ("G-01", "MISSING_REQUIRED") in pairs and ("GF-01", "FORBIDDEN_PRESENT") in pairs
    assert ("B-VTY", "FORBIDDEN_PRESENT") in pairs and ("GF-03", "FORBIDDEN_PRESENT") in pairs
    assert all({"baseline_id", "item_id", "section", "type", "expected", "actual"} <= set(d) for d in r["drifts"])


def test_interface_baseline_drift_and_missing_section():
    base = load_baseline("switch")
    moved = GOOD.replace("switchport access vlan 20\n switchport mode access", "switchport mode trunk")
    r = compare_to_baseline(moved, base)
    items = {(d["item_id"], d["type"]) for d in r["drifts"]}
    assert ("IF-01", "MISSING_REQUIRED") in items and ("IF-01", "FORBIDDEN_PRESENT") in items
    gone = GOOD.replace("interface GigabitEthernet0/1\n", "interface GigabitEthernet0/7\n")
    assert ("IF-01", "MISSING_SECTION") in {(d["item_id"], d["type"]) for d in compare_to_baseline(gone, base)["drifts"]}


def test_optional_interface_absent_is_not_drift():
    cfg = _read("router_good.cfg").replace("GigabitEthernet0/0", "GigabitEthernet0/5")
    assert compare_to_baseline(cfg, load_baseline("router"))["compliant"] is True


def test_interface_abbreviation_matches_baseline():
    cfg = GOOD.replace("interface GigabitEthernet0/1", "interface Gi0/1")
    assert compare_to_baseline(cfg, load_baseline("switch"))["compliant"] is True


# ---------------- diff ----------------
def test_diff_ignores_volatile_lines():
    changed = GOOD.replace("10:21:33 UTC Mon Mar 1 1993", "23:59:59 UTC Fri Dec 31 1993").replace("2488 bytes", "2499 bytes")
    d = diff_configs(GOOD, changed, RULES)
    assert d["changed"] is False and d["changes"] == []


def test_diff_unrelated_change_is_not_security_relevant():
    d = diff_configs(GOOD, GOOD.replace("name IT_DEPT", "name IT_DEPT2"), RULES)
    assert d["changed"] and d["summary"]["security_relevant"] == 0
    assert {(c["change"], c["line"]) for c in d["changes"]} == {("ADDED", "name IT_DEPT2"), ("REMOVED", "name IT_DEPT")}


def test_diff_detects_security_relevant_change_in_block():
    d = diff_configs(GOOD, GOOD.replace("transport input ssh", "transport input telnet", 1), RULES)
    rel = [c for c in d["changes"] if c["security_relevant"]]
    assert len(rel) == 2 and all(c["related_rules"] == ["SEC-002"] for c in rel)
    assert all(c["section"] == "line vty 0 4" for c in rel)


def test_diff_detects_global_line_flip():
    d = diff_configs(GOOD, GOOD.replace("no ip http server\n", "ip http server\n"), RULES)
    assert {(c["change"], c["line"]) for c in d["changes"]} == {("ADDED", "ip http server"), ("REMOVED", "no ip http server")}
    assert all(c["related_rules"] == ["SEC-006"] for c in d["changes"])


def test_diff_section_added_and_removed():
    plus = GOOD + "\ninterface GigabitEthernet0/9\n description test\n"
    d = diff_configs(GOOD, plus, RULES)
    assert [(c["change"], c["section"], c["security_relevant"]) for c in d["changes"]] == [("SECTION_ADDED", "interface GigabitEthernet0/9", False)]
    d2 = diff_configs(plus, GOOD, RULES)
    assert d2["changes"][0]["change"] == "SECTION_REMOVED"
    vty_gone = GOOD.replace("line vty 5 15\n access-class MGMT-ACL in\n exec-timeout 5 0\n logging synchronous\n login local\n transport input ssh\n", "")
    d3 = diff_configs(GOOD, vty_gone, RULES)
    assert d3["changes"][0]["change"] == "SECTION_REMOVED" and d3["changes"][0]["security_relevant"] is True


def test_diff_between_two_stored_snapshots():
    with tempfile.TemporaryDirectory() as d:
        a = save_snapshot(DEV, GOOD, out_dir=d)
        b = save_snapshot(DEV, GOOD.replace("2488 bytes", "2500 bytes"), out_dir=d)
        c = save_snapshot(DEV, GOOD.replace("no ip http server\n", "ip http server\n"), out_dir=d)
        assert a["content_sha256"] == b["content_sha256"] and a["content_sha256"] != c["content_sha256"]
        metas = list_snapshots("Switch-LAB", out_dir=d)
        assert len(metas) == 3
        diff = diff_configs(load_snapshot_text(metas[0], out_dir=d), load_snapshot_text(metas[2], out_dir=d), RULES)
        assert diff["summary"]["security_relevant"] == 2


def test_known_limit_password_change_not_visible_after_sanitizing():
    from app.devices.sanitizer import sanitize_config
    old = sanitize_config("hostname X\nenable secret 5 $1$aaaa$OLDHASH\n")
    new = sanitize_config("hostname X\nenable secret 5 $1$bbbb$NEWHASH\n")
    assert diff_configs(old, new)["changed"] is False     # giới hạn đã biết, được ghi trong tài liệu


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_tests(globals(), "TUẦN 5 - baseline & diff") else 1)
