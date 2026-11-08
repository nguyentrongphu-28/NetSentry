# scripts/verifier_and_evidence.py
"""Bước VERIFY thật + đóng gói evidence có cấu trúc.

Verifier phân tích output 'show vlan brief' và 'show interfaces <if> switchport'
rồi SO SÁNH với giá trị mong đợi. Kết quả PASS chỉ khi mọi kiểm tra đều đạt;
output rỗng/không đọc được cho kết quả ERROR (không bao giờ mặc định PASS).
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

from app.audit.config_parser import normalize_interface_name
from app.devices.network_adapter import IOS_ERROR_RX
from app.core.paths import REPORT_DIR
from app.devices.sanitizer import sanitize_config

_VLAN_ROW = re.compile(r"^(\d{1,4})\s+(\S+)\s+(\S+)\s*(.*)$")


def parse_show_vlan_brief(text):
    """-> {vlan_id(int): {'name','status','ports':[tên đầy đủ]}} (xử lý cả dòng port bị xuống hàng)."""
    vlans, current = {}, None
    for line in (text or "").splitlines():
        if not line.strip() or line.startswith("VLAN Name") or line.startswith("----"):
            continue
        m = _VLAN_ROW.match(line)
        if m and not line.startswith((" ", "\t")):
            current = int(m.group(1))
            vlans[current] = {"name": m.group(2), "status": m.group(3), "ports": []}
            ports_txt = m.group(4)
        elif line.startswith((" ", "\t")) and current is not None:
            ports_txt = line
        else:
            continue
        for p in ports_txt.split(","):
            p = p.strip()
            if p:
                vlans[current]["ports"].append(normalize_interface_name(p))
    return vlans


def parse_switchport(text):
    def grab(rx):
        m = re.search(rx, text or "", re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None
    vlan = grab(r"^Access Mode VLAN:\s*(\d+)")
    return {
        "name": grab(r"^Name:\s*(\S+)"),
        "switchport": grab(r"^Switchport:\s*(\S+)"),
        "admin_mode": grab(r"^Administrative Mode:\s*(.+)$"),
        "operational_mode": grab(r"^Operational Mode:\s*(.+)$"),
        "access_vlan": int(vlan) if vlan else None,
    }


def vlan_exists(vlan_brief_output, vlan_id):
    return int(vlan_id) in parse_show_vlan_brief(vlan_brief_output)


def verify_vlan_outputs(vlan_brief_out, switchport_out, vlan_id, vlan_name, interface):
    """So sánh output thật với kỳ vọng. Trả về dict có verification_status PASS/FAIL/ERROR."""
    vid = int(vlan_id)
    iface = normalize_interface_name(interface)
    vlans = parse_show_vlan_brief(vlan_brief_out)
    sp = parse_switchport(switchport_out)

    if not vlans or IOS_ERROR_RX.search(vlan_brief_out or ""):
        return {"verification_status": "ERROR", "checks": [], "parsed_result": {},
                "reason": "Không đọc được output 'show vlan brief'"}
    if sp["name"] is None or IOS_ERROR_RX.search(switchport_out or ""):
        return {"verification_status": "ERROR", "checks": [], "parsed_result": {"vlans_seen": sorted(vlans)},
                "reason": "Không đọc được output 'show interfaces switchport'"}

    row = vlans.get(vid)
    checks = [
        {"name": "vlan_exists", "expected": vid, "actual": vid if row else None, "passed": row is not None},
        {"name": "vlan_name", "expected": vlan_name, "actual": row["name"] if row else None,
         "passed": bool(row) and row["name"] == vlan_name},
        {"name": "vlan_active", "expected": "active", "actual": row["status"] if row else None,
         "passed": bool(row) and row["status"] == "active"},
        {"name": "port_in_vlan", "expected": iface, "actual": row["ports"] if row else None,
         "passed": bool(row) and iface in row["ports"]},
        {"name": "admin_mode_access", "expected": "static access", "actual": sp["admin_mode"],
         "passed": (sp["admin_mode"] or "").lower() == "static access"},
        {"name": "access_vlan", "expected": vid, "actual": sp["access_vlan"], "passed": sp["access_vlan"] == vid},
    ]
    parsed = {
        "vlan_id": str(vid),
        "vlan_name": row["name"] if row else None,
        "status": row["status"] if row else None,
        "assigned_ports": row["ports"] if row else [],
        "switchport": sp,
    }
    return {"verification_status": "PASS" if all(c["passed"] for c in checks) else "FAIL",
            "checks": checks, "parsed_result": parsed}


def verify_vlan(run_show, vlan_id, vlan_name, interface):
    """run_show: hàm nhận lệnh 'show ...' trả về output (vd NetworkAdapter.run_show)."""
    iface = normalize_interface_name(interface)
    outs = {"vlan_brief": run_show("show vlan brief"),
            "switchport": run_show(f"show interfaces {iface} switchport")}
    result = verify_vlan_outputs(outs["vlan_brief"], outs["switchport"], vlan_id, vlan_name, iface)
    result["raw_outputs"] = outs
    return result


def generate_task_evidence(task_id, device_name, model, ios_version, commands_sent, *,
                           device_id=None, task_name="Create VLAN and Assign Port",
                           execution_output=None, verify_outputs=None, expected=None,
                           approved_by=None, rollback_commands=None, executed_at=None):
    """Đóng gói evidence. Trạng thái được SUY RA từ output thật, không gán cứng."""
    if execution_output is None:
        exec_status, exec_errors = "NOT_EXECUTED", []
    else:
        exec_errors = [m.group(0) for m in re.finditer(r"^%.*$", execution_output, re.MULTILINE) if IOS_ERROR_RX.match(m.group(0))]
        exec_status = "FAILED" if exec_errors else "SUCCESS"

    if verify_outputs is None or expected is None:
        verification = {"verification_status": "NOT_RUN", "checks": [], "parsed_result": {}}
    else:
        verification = verify_vlan_outputs(verify_outputs.get("vlan_brief"), verify_outputs.get("switchport"),
                                           expected["vlan_id"], expected["vlan_name"], expected["interface"])
    vstatus = verification["verification_status"]
    overall = exec_status if exec_status in ("FAILED", "NOT_EXECUTED") else vstatus

    safe_verify_raw = {k: sanitize_config(v) for k, v in (verify_outputs or {}).items()}
    return {
        "task_metadata": {
            "task_id": task_id,
            "task_name": task_name,
            "target_device": device_name,
            "device_id": device_id,
            "device_model": model,
            "ios_version": ios_version,
            "approved_by": approved_by,
            "executed_at": executed_at or datetime.now(timezone.utc).isoformat(),
        },
        "execution_payload": {
            "status": exec_status,
            "commands_sent": list(commands_sent),
            "commands_sha256": hashlib.sha256("\n".join(commands_sent).encode("utf-8")).hexdigest(),
            "raw_cli_output": sanitize_config(execution_output or ""),
            "errors": exec_errors,
            "rollback_commands": list(rollback_commands or []),
        },
        "verification_steps": {
            "verify_commands": ["show vlan brief", f"show interfaces {expected['interface']} switchport"] if expected else [],
            "raw_outputs": safe_verify_raw,
            "parsed_result": verification.get("parsed_result", {}),
            "checks": verification.get("checks", []),
            "reason": verification.get("reason"),
            "verification_status": vstatus,
        },
        "overall_status": overall,
    }


def save_evidence(evidence, out_dir=None):
    out_dir = str(out_dir or REPORT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", evidence["task_metadata"]["task_id"])
    path = os.path.join(out_dir, f"evidence_{safe}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    return path
