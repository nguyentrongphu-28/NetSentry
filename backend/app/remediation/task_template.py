# scripts/task_template.py
"""Template tác vụ 'Tạo VLAN và gán cổng access' trên Cisco IOS.

Mọi tham số đều được validate trước khi sinh lệnh (chống chèn lệnh, chống đụng
uplink/VLAN ngoài phạm vi lab). Template KHÔNG chứa 'configure terminal', 'end'
hay 'write memory': Netmiko send_config_set tự vào/thoát config mode, và việc
lưu cấu hình chỉ làm SAU khi bước verify đạt.
"""
import json
import re

from app.audit.config_parser import get_interface_block, normalize_interface_name, parse_config
from app.core.paths import POLICY_PATH

ACTION_TYPE = "create_vlan_assign_access_port"
RESERVED_VLANS = {1, 1002, 1003, 1004, 1005}
VLAN_NAME_RX = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
IFACE_RX = re.compile(r"^(FastEthernet|GigabitEthernet)\d+(/\d+){1,2}$")
_CTRL_RX = re.compile(r"[\x00-\x1f\x7f]")


class TaskValidationError(ValueError):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def load_policy(path=None):
    with open(str(path or POLICY_PATH), "r", encoding="utf-8") as f:
        return json.load(f)


def validate_vlan_params(vlan_id, vlan_name, interface_name, policy=None):
    """Trả về tham số đã chuẩn hóa hoặc raise TaskValidationError (liệt kê mọi lỗi)."""
    policy = policy if policy is not None else load_policy()
    errors = []

    vid = None
    if isinstance(vlan_id, bool) or not isinstance(vlan_id, (int, str)):
        errors.append("vlan_id phải là số nguyên")
    else:
        s = str(vlan_id).strip()
        if not re.fullmatch(r"\d{1,4}", s):
            errors.append(f"vlan_id không hợp lệ: {vlan_id!r}")
        else:
            vid = int(s)
            if not 1 <= vid <= 4094:
                errors.append(f"vlan_id {vid} ngoài khoảng 1-4094")
            elif vid in RESERVED_VLANS:
                errors.append(f"vlan_id {vid} là VLAN mặc định/dành riêng, không được dùng")
            else:
                rng = policy.get("allowed_vlan_ids", {})
                if not (rng.get("min", 0) <= vid <= rng.get("max", -1)):
                    errors.append(f"vlan_id {vid} nằm ngoài phạm vi lab cho phép ({rng.get('min')}-{rng.get('max')})")

    name = vlan_name if isinstance(vlan_name, str) else ""
    if not VLAN_NAME_RX.fullmatch(name):
        errors.append("vlan_name chỉ gồm chữ, số, '_' hoặc '-' (tối đa 32 ký tự, không xuống dòng/khoảng trắng)")

    iface = None
    if not isinstance(interface_name, str) or _CTRL_RX.search(interface_name):
        errors.append("interface_name không hợp lệ")
    else:
        iface = normalize_interface_name(interface_name.strip())
        if not IFACE_RX.fullmatch(iface):
            errors.append(f"interface '{interface_name}' không phải FastEthernet/GigabitEthernet hợp lệ")
            iface = None
        else:
            protected = {normalize_interface_name(x) for x in policy.get("protected_interfaces", [])}
            allowed = {normalize_interface_name(x) for x in policy.get("allowed_interfaces", [])}
            if iface in protected:
                errors.append(f"{iface} là interface được bảo vệ (uplink/đang vận hành)")
            elif iface not in allowed:
                errors.append(f"{iface} không nằm trong danh sách interface được phép thử nghiệm")

    if errors:
        raise TaskValidationError(errors)
    return {"vlan_id": vid, "vlan_name": name, "interface_name": iface}


def get_vlan_template(vlan_id, vlan_name, interface_name, policy=None):
    """Danh sách lệnh CẤU HÌNH (đã validate) để gửi qua send_config_set."""
    p = validate_vlan_params(vlan_id, vlan_name, interface_name, policy)
    return [
        f"vlan {p['vlan_id']}",
        f" name {p['vlan_name']}",
        "exit",
        f"interface {p['interface_name']}",
        " switchport mode access",
        f" switchport access vlan {p['vlan_id']}",
        " no shutdown",
    ]


def build_vlan_task(vlan_id, vlan_name, interface_name, policy=None):
    """Gói đầy đủ cho workflow Preview -> Validate -> Approve -> Execute -> Verify."""
    p = validate_vlan_params(vlan_id, vlan_name, interface_name, policy)
    iface = p["interface_name"]
    return {
        "action_type": ACTION_TYPE,
        "params": p,
        "pre_check_commands": ["show vlan brief", f"show running-config interface {iface}"],
        "config_commands": get_vlan_template(vlan_id, vlan_name, interface_name, policy),
        "verify_commands": ["show vlan brief", f"show interfaces {iface} switchport"],
        "save_after_verify": True,
    }


def build_rollback_commands(params, pre_interface_output, vlan_existed_before):
    """Sinh lệnh rollback từ cấu hình interface CHỤP TRƯỚC khi đổi.

    Từ chối (raise) nếu không có cấu hình trước thay đổi: không rollback mù.
    """
    iface = params["interface_name"]
    block = get_interface_block(parse_config(pre_interface_output or ""), iface)
    if block is None:
        raise TaskValidationError([f"Không thấy 'interface {iface}' trong cấu hình trước thay đổi; không thể lập rollback an toàn"])
    cmds = [f"default interface {iface}", f"interface {iface}"] + [f" {c}" for c in block.children]
    if not vlan_existed_before:
        cmds += ["exit", f"no vlan {params['vlan_id']}"]
    return cmds


if __name__ == "__main__":
    print("[*] Template tạo VLAN (đã validate):")
    for c in get_vlan_template(20, "IT_DEPT", "Gi0/1"):
        print(c)
