# scripts/inventory_loader.py
import ipaddress
import json
import os

from app.core.paths import INVENTORY_PATH

REQUIRED_FIELDS = ("id", "name", "ip", "device_type")
VALID_ROLES = ("router", "switch")


def validate_device(dev):
    """Trả về danh sách lỗi của một thiết bị (rỗng nếu hợp lệ)."""
    errors = []
    if not isinstance(dev, dict):
        return ["Phần tử không phải object JSON"]
    for field in REQUIRED_FIELDS:
        if not str(dev.get(field, "")).strip():
            errors.append(f"thiếu trường '{field}'")
    ip = str(dev.get("ip", "")).strip()
    if ip:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            errors.append(f"IP không hợp lệ: '{ip}'")
    role = dev.get("role")
    if role is not None and role not in VALID_ROLES:
        errors.append(f"role phải là một trong {VALID_ROLES}, nhận được '{role}'")
    return errors


def load_inventory(file_path=None, verbose=True):
    """Đọc và kiểm tra inventory.json. Thiết bị lỗi bị loại và được báo rõ lý do."""
    file_path = str(file_path or INVENTORY_PATH)
    if not os.path.exists(file_path):
        if verbose:
            print(f"[-] Không tìm thấy file inventory tại: {file_path}")
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        if verbose:
            print(f"[-] Lỗi định dạng JSON trong file inventory: {e}")
        return []
    if not isinstance(raw, list):
        if verbose:
            print("[-] inventory phải là một mảng JSON các thiết bị")
        return []

    devices, seen_ids, seen_names = [], set(), set()
    for i, dev in enumerate(raw):
        errs = validate_device(dev)
        if not errs:
            if dev["id"] in seen_ids:
                errs.append(f"trùng id '{dev['id']}'")
            if dev["name"] in seen_names:
                errs.append(f"trùng name '{dev['name']}'")
        if errs:
            if verbose:
                print(f"[-] Bỏ qua thiết bị #{i}: " + "; ".join(errs))
            continue
        seen_ids.add(dev["id"])
        seen_names.add(dev["name"])
        devices.append(dev)

    if verbose:
        print(f"[✓] Đã tải {len(devices)}/{len(raw)} thiết bị hợp lệ từ inventory.")
        for d in devices:
            print(f"    - {d['name']} | IP: {d['ip']} | Loại: {d['device_type']} | Role: {d.get('role', '?')}")
    return devices


def get_device(key, devices=None):
    """Tìm thiết bị theo id hoặc name."""
    devices = devices if devices is not None else load_inventory(verbose=False)
    for d in devices:
        if key in (d.get("id"), d.get("name")):
            return d
    return None


if __name__ == "__main__":
    load_inventory()
