"""Kiểm tra tham số tác vụ theo lab_policy.json. Fail-closed: thiếu/hỏng policy => từ chối mọi thứ."""
import json
import re

RESERVED_VLANS = {1, 1002, 1003, 1004, 1005}
_IFACE = re.compile(r"^(fa|fastethernet|gi|gigabitethernet)\s*(\d+/\d+(?:/\d+)?)$", re.I)
_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}")   # dùng fullmatch: "$" sẽ chấp nhận "LAB\n"
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def canonical_interface(name):
    """'gi0/1' -> 'GigabitEthernet0/1'. Trả None nếu không phải Fa/Gi (Te, Po, Vlan, Loopback... bị loại)."""
    m = _IFACE.fullmatch((name or "").strip())
    if not m:
        return None
    kind = "FastEthernet" if m.group(1).lower().startswith("fa") else "GigabitEthernet"
    return kind + m.group(2)


def load_policy(path):
    """Đọc policy; lỗi => PolicyGate rỗng (từ chối tất cả)."""
    try:
        with open(path, encoding="utf-8") as f:
            return PolicyGate(json.load(f))
    except (OSError, ValueError):
        return PolicyGate({})


class PolicyGate:
    def __init__(self, policy: dict):
        p = policy if isinstance(policy, dict) else {}
        vr = p.get("allowed_vlan_ids") or {}
        self.vlan_min = vr.get("min") if isinstance(vr.get("min"), int) else None
        self.vlan_max = vr.get("max") if isinstance(vr.get("max"), int) else None
        self.allowed = {canonical_interface(i) for i in p.get("allowed_interfaces", []) if canonical_interface(i)}
        self.protected = {canonical_interface(i) for i in p.get("protected_interfaces", []) if canonical_interface(i)}

    def check_vlan_params(self, params: dict) -> list:
        """Trả danh sách mã lỗi (rỗng = hợp lệ)."""
        errs = []
        if not isinstance(params, dict):
            return ["params_not_object"]
        vid, name, iface = params.get("vlan_id"), params.get("name"), params.get("interface")
        if isinstance(vid, bool) or not isinstance(vid, int):
            errs.append("vlan_id_not_int")
        else:
            if vid in RESERVED_VLANS:
                errs.append("vlan_id_reserved")
            if self.vlan_min is None or self.vlan_max is None:
                errs.append("policy_missing_vlan_range")
            elif not (self.vlan_min <= vid <= self.vlan_max):
                errs.append("vlan_id_outside_policy")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            errs.append("vlan_name_invalid")
        canon = canonical_interface(iface) if isinstance(iface, str) and not _CTRL.search(iface) else None
        if canon is None:
            errs.append("interface_type_not_supported")
        else:
            if canon in self.protected:
                errs.append("interface_protected")
            if canon not in self.allowed:
                errs.append("interface_not_in_allowed_list")
        return errs

    def normalize_vlan_params(self, params: dict) -> dict:
        out = dict(params)
        out["interface"] = canonical_interface(params.get("interface")) or params.get("interface")
        return out
