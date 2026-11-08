# scripts/syntax_validator.py
"""Kiểm tra danh sách lệnh trước khi gửi: allowlist + ngữ cảnh + phiên bản IOS + model/role.

validate_ios_syntax(commands, ios_version, model=None, device_role=None, policy=None, mode="config")
  mode="config"   : chỉ cho phép đúng các lệnh của tác vụ tạo VLAN/gán port access.
  mode="rollback" : thêm 'default interface X', 'no vlan N' và các dòng con của interface.
"""
import re

from app.audit.config_parser import normalize_interface_name

# Bảng đặc tính theo model. Chỉ ghi những gì đã biết chắc; bổ sung khi xác minh model thật.
MODEL_PROFILES = {
    "2960": {"role": "switch", "interface_prefixes": ("FastEthernet", "GigabitEthernet")},
}

_CTRL_RX = re.compile(r"[\x00-\x1f\x7f?]")
_IFACE = r"(?:FastEthernet|GigabitEthernet)\d+(?:/\d+){1,2}"
ALLOW = {
    "vlan": re.compile(r"^vlan (\d{1,4})$"),
    "name": re.compile(r"^name [A-Za-z0-9_-]{1,32}$"),
    "exit": re.compile(r"^exit$"),
    "interface": re.compile(rf"^interface ({_IFACE})$"),
    "mode_access": re.compile(r"^switchport mode access$"),
    "access_vlan": re.compile(r"^switchport access vlan (\d{1,4})$"),
    "no_shutdown": re.compile(r"^no shutdown$"),
}
ROLLBACK_ONLY = {
    "default_if": re.compile(rf"^default interface ({_IFACE})$"),
    "no_vlan": re.compile(r"^no vlan (\d{1,4})$"),
}
DANGEROUS_RX = re.compile(r"^(reload|erase|delete|format|write|copy|boot|crypto|username|enable|aaa|clear|snmp-server|line|no\s+interface)\b", re.IGNORECASE)


def parse_ios_version(ios_version):
    """'15.2(4)E7' -> (15, 2); '12.2(55)SE' -> (12, 2); '16.9.4' -> (16, 9)."""
    m = re.match(r"^\s*(\d+)\.(\d+)", str(ios_version or ""))
    if not m:
        raise ValueError(f"Không đọc được phiên bản IOS: {ios_version!r}")
    return int(m.group(1)), int(m.group(2))


def _profile_for(model):
    for key, prof in MODEL_PROFILES.items():
        if model and key in str(model):
            return prof
    return None


def _vlan_ok(vid, policy):
    """Trả về thông báo lỗi hoặc None."""
    if not 1 <= vid <= 4094:
        return f"VLAN {vid} ngoài khoảng 1-4094"
    if vid in (1, 1002, 1003, 1004, 1005):
        return f"VLAN {vid} là VLAN mặc định/dành riêng"
    if policy is not None:
        rng = policy.get("allowed_vlan_ids", {})
        if not (rng.get("min", 0) <= vid <= rng.get("max", -1)):
            return f"VLAN {vid} nằm ngoài phạm vi lab cho phép"
    return None


def validate_ios_syntax(commands, ios_version="15.0", model=None, device_role=None, policy=None, mode="config"):
    errors, warnings = [], []
    if not isinstance(commands, (list, tuple)) or not commands:
        return {"status": "INVALID", "errors": ["Danh sách lệnh rỗng hoặc sai kiểu"], "warnings": []}
    if mode not in ("config", "rollback"):
        return {"status": "INVALID", "errors": [f"mode không hợp lệ: {mode}"], "warnings": []}

    try:
        ver = parse_ios_version(ios_version)
    except ValueError as e:
        return {"status": "INVALID", "errors": [str(e)], "warnings": []}

    profile = _profile_for(model)
    role = device_role or (profile or {}).get("role")
    if model and profile is None:
        warnings.append(f"Chưa có hồ sơ cho model '{model}': bỏ qua kiểm tra tiền tố interface theo model")
    prefixes = (profile or {}).get("interface_prefixes")

    ctx, current_if, mode_access, created_vlans = None, None, False, set()

    for idx, raw in enumerate(commands):
        if not isinstance(raw, str):
            errors.append(f"Lỗi dòng {idx}: lệnh phải là chuỗi")
            continue
        if _CTRL_RX.search(raw):
            errors.append(f"Lỗi dòng {idx}: chứa ký tự điều khiển/xuống dòng/'?'")
            continue
        cmd = raw.strip()
        if not cmd or len(cmd) > 200:
            errors.append(f"Lỗi dòng {idx}: lệnh rỗng hoặc quá dài")
            continue

        # Quy tắc: 'vlan database' đã lỗi thời từ IOS 12.2 trở lên
        if re.match(r"^vlan\s+database\b", cmd, re.IGNORECASE):
            if ver >= (12, 2):
                errors.append(f"Lỗi dòng {idx}: 'vlan database' đã lỗi thời trên IOS {ios_version}; dùng 'vlan <ID>' trong config mode.")
            else:
                errors.append(f"Lỗi dòng {idx}: 'vlan database' không nằm trong allowlist của tác vụ.")
            continue

        # Chấp nhận tên interface viết tắt (Gi0/1 -> GigabitEthernet0/1) trước khi so khớp allowlist
        m_if = re.match(r"^(interface|default interface)\s+(\S+)$", cmd, re.IGNORECASE)
        if m_if:
            cmd = f"{m_if.group(1).lower()} {normalize_interface_name(m_if.group(2))}"

        matched = next((k for k, rx in ALLOW.items() if rx.match(cmd)), None)
        if matched is None and mode == "rollback":
            matched = next((k for k, rx in ROLLBACK_ONLY.items() if rx.match(cmd)), None)
            if matched is None and ctx == "interface" and not DANGEROUS_RX.match(cmd):
                matched = "rollback_interface_line"
        if matched is None:
            why = "lệnh nguy hiểm/không được phép" if DANGEROUS_RX.match(cmd) else "không nằm trong allowlist"
            errors.append(f"Lỗi dòng {idx}: '{cmd}' - {why}.")
            continue

        if matched == "vlan":
            vid = int(ALLOW["vlan"].match(cmd).group(1))
            msg = _vlan_ok(vid, policy)
            if msg:
                errors.append(f"Lỗi dòng {idx}: {msg}.")
            created_vlans.add(vid)
            ctx = "vlan"
        elif matched == "name":
            if ctx != "vlan":
                errors.append(f"Lỗi dòng {idx}: 'name' chỉ hợp lệ ngay sau 'vlan <ID>'.")
        elif matched == "exit":
            ctx, current_if, mode_access = None, None, False
        elif matched == "interface":
            iface = ALLOW["interface"].match(cmd).group(1)
            ctx, current_if, mode_access = "interface", normalize_interface_name(iface), False
            if prefixes and not iface.startswith(prefixes):
                errors.append(f"Lỗi dòng {idx}: model {model} không có interface kiểu '{iface}'.")
            if policy is not None:
                prot = {normalize_interface_name(x) for x in policy.get("protected_interfaces", [])}
                allow = {normalize_interface_name(x) for x in policy.get("allowed_interfaces", [])}
                if current_if in prot:
                    errors.append(f"Lỗi dòng {idx}: {current_if} là interface được bảo vệ.")
                elif current_if not in allow:
                    errors.append(f"Lỗi dòng {idx}: {current_if} không nằm trong danh sách interface được phép.")
        elif matched in ("mode_access", "access_vlan", "no_shutdown", "rollback_interface_line"):
            if ctx != "interface":
                errors.append(f"Lỗi dòng {idx}: '{cmd}' chỉ hợp lệ trong ngữ cảnh interface.")
            if role == "router" and cmd.startswith("switchport"):
                errors.append(f"Lỗi dòng {idx}: router không hỗ trợ lệnh 'switchport' (cổng L3).")
            if matched == "mode_access":
                mode_access = True
            if matched == "access_vlan":
                vid = int(ALLOW["access_vlan"].match(cmd).group(1))
                msg = _vlan_ok(vid, policy)
                if msg:
                    errors.append(f"Lỗi dòng {idx}: {msg}.")
                if mode == "config" and not mode_access:
                    errors.append(f"Lỗi dòng {idx}: Thiếu lệnh 'switchport mode access' trước khi gán VLAN (trong cùng interface).")
                if mode == "config" and vid not in created_vlans:
                    warnings.append(f"Dòng {idx}: VLAN {vid} chưa được khai báo trong cùng tác vụ.")
        elif matched == "default_if":
            iface = normalize_interface_name(ROLLBACK_ONLY["default_if"].match(cmd).group(1))
            if policy is not None:
                allow = {normalize_interface_name(x) for x in policy.get("allowed_interfaces", [])}
                if iface not in allow:
                    errors.append(f"Lỗi dòng {idx}: {iface} không nằm trong danh sách interface được phép.")
            ctx = None
        elif matched == "no_vlan":
            vid = int(ROLLBACK_ONLY["no_vlan"].match(cmd).group(1))
            msg = _vlan_ok(vid, policy)
            if msg:
                errors.append(f"Lỗi dòng {idx}: {msg}.")

    if errors:
        return {"status": "INVALID", "errors": errors, "warnings": warnings}
    return {"status": "VALID", "message": "Cú pháp hợp lệ theo allowlist và phiên bản/model đã khai báo.", "errors": [], "warnings": warnings}


if __name__ == "__main__":
    print(validate_ios_syntax(["vlan 20", " name IT_DEPT", "exit", "interface Gi0/1", "switchport access vlan 20"], "15.2"))
