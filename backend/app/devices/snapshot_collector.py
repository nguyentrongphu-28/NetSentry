# scripts/snapshot_collector.py
"""Thu thập snapshot cấu hình: kết nối -> lấy running-config -> LÀM SẠCH -> lưu.

Chỉ bản ĐÃ LÀM SẠCH được ghi ra đĩa (không bao giờ lưu cấu hình thô).
Mỗi snapshot gồm 2 file: <tên>_<UTC>.cfg và <tên>_<UTC>.meta.json.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

from app.audit.config_parser import normalize_lines
from app.devices.inventory_loader import get_device, load_inventory
from app.devices.network_adapter import AdapterError, NetworkAdapter, parse_show_version
from app.core.paths import SNAPSHOT_DIR
from app.devices.sanitizer import sanitize_config_with_stats


def _safe_name(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s))


def _atomic_write(path, text):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def save_snapshot(device, config_text, info=None, out_dir=None, collected_at=None, source="device"):
    """Làm sạch rồi lưu snapshot. Trả về metadata (dict)."""
    if not config_text or not config_text.strip():
        raise AdapterError("COMMAND", "Cấu hình rỗng, không lưu snapshot.")
    out_dir = str(out_dir or SNAPSHOT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    collected_at = collected_at or datetime.now(timezone.utc)
    stamp = collected_at.strftime("%Y%m%dT%H%M%SZ")

    clean, redactions = sanitize_config_with_stats(config_text)
    base = f"{_safe_name(device['name'])}_{stamp}"
    n = 1
    while os.path.exists(os.path.join(out_dir, base + ".cfg")):
        n += 1
        base = f"{_safe_name(device['name'])}_{stamp}_{n}"

    info = info or {}
    meta = {
        "snapshot_id": base,
        "device_id": device["id"],
        "device_name": device["name"],
        "ip": device["ip"],
        "role": device.get("role"),
        "collected_at": collected_at.isoformat(),
        "source": source,
        "hostname": info.get("hostname"),
        "model": info.get("model"),
        "ios_version": info.get("ios_version"),
        "serial": info.get("serial"),
        "redactions": redactions,
        "line_count": len(clean.splitlines()),
        "sha256": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
        # Hash trên nội dung đã bỏ dòng 'dễ đổi' -> dùng để biết cấu hình có thật sự đổi không
        "content_sha256": hashlib.sha256("\n".join(normalize_lines(clean)).encode("utf-8")).hexdigest(),
        "file": base + ".cfg",
    }
    _atomic_write(os.path.join(out_dir, base + ".cfg"), clean if clean.endswith("\n") else clean + "\n")
    _atomic_write(os.path.join(out_dir, base + ".meta.json"), json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def collect_snapshot(device, adapter_factory=NetworkAdapter, out_dir=None, **adapter_kwargs):
    """Thu thập 1 thiết bị. Không raise: trả {'ok': bool, ...} để lặp nhiều thiết bị."""
    try:
        with adapter_factory(device, **adapter_kwargs) as adapter:
            info = adapter.get_device_info()
            cfg = adapter.get_running_config()
        meta = save_snapshot(device, cfg, info=info, out_dir=out_dir)
        return {"ok": True, "device": device["name"], "snapshot": meta}
    except AdapterError as e:
        return {"ok": False, "device": device["name"], **e.to_dict()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "device": device["name"], "error_type": "UNKNOWN", "message": f"{type(e).__name__}: {e}"}


def collect_all(devices=None, **kwargs):
    devices = devices if devices is not None else load_inventory(verbose=False)
    return [collect_snapshot(d, **kwargs) for d in devices]


def list_snapshots(device_name, out_dir=None):
    """Danh sách metadata snapshot của một thiết bị, cũ -> mới."""
    out_dir = str(out_dir or SNAPSHOT_DIR)
    if not os.path.isdir(out_dir):
        return []
    metas = []
    prefix = _safe_name(device_name) + "_"
    for fn in os.listdir(out_dir):
        if fn.startswith(prefix) and fn.endswith(".meta.json"):
            with open(os.path.join(out_dir, fn), "r", encoding="utf-8") as f:
                metas.append(json.load(f))
    return sorted(metas, key=lambda m: (m["collected_at"], m["snapshot_id"]))


def load_snapshot_text(meta, out_dir=None):
    with open(os.path.join(str(out_dir or SNAPSHOT_DIR), meta["file"]), "r", encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Thu thập snapshot cấu hình Cisco")
    ap.add_argument("--device", help="id hoặc tên thiết bị (mặc định: tất cả trong inventory)")
    ap.add_argument("--from-file", help="Lưu snapshot từ file cấu hình có sẵn (không cần kết nối)")
    args = ap.parse_args(argv)

    if args.from_file:
        if not args.device:
            ap.error("--from-file cần đi kèm --device")
        dev = get_device(args.device)
        if not dev:
            print(f"[-] Không thấy thiết bị '{args.device}' trong inventory")
            return 1
        with open(args.from_file, "r", encoding="utf-8") as f:
            meta = save_snapshot(dev, f.read(), source="file")
        print(f"[✓] Đã lưu snapshot: {meta['file']} (đã che {meta['redactions']} vị trí nhạy cảm)")
        return 0

    devices = load_inventory(verbose=False)
    if args.device:
        dev = get_device(args.device, devices)
        devices = [dev] if dev else []
    if not devices:
        print("[-] Không có thiết bị nào để thu thập")
        return 1
    rc = 0
    for res in collect_all(devices):
        if res["ok"]:
            m = res["snapshot"]
            print(f"[✓] {res['device']}: {m['file']} | {m['model']} | IOS {m['ios_version']} | che {m['redactions']} vị trí")
        else:
            rc = 2
            print(f"[-] {res['device']}: {res['error_type']} - {res['message']}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
