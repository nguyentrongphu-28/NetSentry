# scripts/network_adapter.py
"""Lớp kết nối thiết bị Cisco qua SSH (Netmiko).

- Mặc định CHỈ ĐỌC: run_show() chỉ cho phép lệnh 'show ...'.
- Ghi cấu hình chỉ qua apply_config()/save_config(), do workflow đã được duyệt gọi.
- Mọi lỗi kết nối được phân loại thành AdapterError(error_type, message) với
  error_type ∈ TIMEOUT | AUTH | CONNECTION | COMMAND | CONFIG | UNKNOWN.
- Tài khoản lấy từ biến môi trường / file .env, KHÔNG nằm trong inventory hay code.
"""
import os
import re
import time

from app.core.paths import PROJECT_ROOT

IOS_ERROR_RX = re.compile(r"^%\s*(Invalid input|Incomplete command|Ambiguous command|Unknown command|Error)", re.IGNORECASE | re.MULTILINE)
# Chỉ cho phép dấu cách thường (KHÔNG dùng \s: nó khớp cả '\n'/'\r' nên 'show version\nreload' từng lọt qua cổng chỉ-đọc)
_SHOW_RX = re.compile(r"show +[\w\-/.: ]+(\| *(?:include|exclude|begin|section) +[\w\-/.:^$ ]+)?", re.IGNORECASE)


class AdapterError(Exception):
    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type
        self.message = message

    def to_dict(self):
        return {"error_type": self.error_type, "message": self.message}


def load_env(path=None):
    """Đọc file .env đơn giản (KEY=VALUE). Biến môi trường thật được ưu tiên."""
    path = path or (PROJECT_ROOT / ".env")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


def get_credentials():
    load_env()
    user = os.environ.get("NETSENTRY_USERNAME", "")
    pwd = os.environ.get("NETSENTRY_PASSWORD", "")
    secret = os.environ.get("NETSENTRY_ENABLE_SECRET", "")
    if not user or not pwd:
        raise AdapterError("CONFIG", "Thiếu NETSENTRY_USERNAME/NETSENTRY_PASSWORD (xem .env.example).")
    return user, pwd, secret


def classify_exception(exc):
    """Phân loại exception của Netmiko/socket mà không cần import cứng Netmiko."""
    name = type(exc).__name__
    if "Authentication" in name:
        return "AUTH"
    if "Timeout" in name or isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, (OSError, ConnectionError)) or "Connection" in name or "SSH" in name:
        return "CONNECTION"
    return "UNKNOWN"


def parse_show_version(text):
    """Trích hostname, model, phiên bản IOS, serial, uptime từ 'show version'."""
    def grab(pattern, flags=re.IGNORECASE | re.MULTILINE):
        m = re.search(pattern, text or "", flags)
        return m.group(1).strip() if m else None

    model = grab(r"^Model\s+[Nn]umber\s*:\s*(\S+)") or grab(r"^cisco\s+(\S+)\s+\(.*?\)\s+(?:processor|with)")
    return {
        "hostname": grab(r"^(\S+)\s+uptime is"),
        "model": model,
        "ios_version": grab(r"\bVersion\s+(\d[^\s,]*)"),
        "serial": grab(r"System\s+[Ss]erial\s+[Nn]umber\s*:\s*(\S+)") or grab(r"Processor board ID\s+(\S+)"),
        "uptime": grab(r"uptime is\s+(.+)"),
    }


def _netmiko_factory(params):
    try:
        from netmiko import ConnectHandler
    except ImportError as e:
        raise AdapterError("CONFIG", "Chưa cài netmiko: pip install netmiko") from e
    return ConnectHandler(**params)


class NetworkAdapter:
    def __init__(self, device, username=None, password=None, secret=None,
                 timeout=20, connection_factory=None):
        self.device = device
        self._creds = (username, password, secret)
        self.timeout = timeout
        self._factory = connection_factory or _netmiko_factory
        self.conn = None

    # --- vòng đời kết nối -------------------------------------------------
    def connect(self):
        user, pwd, secret = self._creds
        if not user or not pwd:
            user, pwd, secret = get_credentials()
        params = {
            "device_type": self.device["device_type"],
            "host": self.device["ip"],
            "username": user,
            "password": pwd,
            "secret": secret or "",
            "timeout": self.timeout,
            "conn_timeout": self.timeout,
            "auth_timeout": self.timeout,
            "banner_timeout": self.timeout,
        }
        try:
            self.conn = self._factory(params)
            if secret and not self.conn.check_enable_mode():
                self.conn.enable()
        except AdapterError:
            raise
        except Exception as e:  # noqa: BLE001
            self.conn = None
            raise AdapterError(classify_exception(e), f"{type(e).__name__}: {e}") from e
        return self

    def disconnect(self):
        if self.conn is not None:
            try:
                self.conn.disconnect()
            except Exception:  # noqa: BLE001 - đóng kết nối không được làm hỏng luồng chính
                pass
            self.conn = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.disconnect()

    def _require_conn(self):
        if self.conn is None:
            raise AdapterError("CONNECTION", "Chưa kết nối tới thiết bị.")

    # --- chỉ đọc -----------------------------------------------------------
    def run_show(self, command, read_timeout=60):
        command = (command or "").strip()
        if not _SHOW_RX.fullmatch(command):
            raise AdapterError("COMMAND", f"Chỉ cho phép lệnh 'show' chỉ đọc, nhận được: {command!r}")
        self._require_conn()
        try:
            out = self.conn.send_command(command, read_timeout=read_timeout)
        except Exception as e:  # noqa: BLE001
            raise AdapterError(classify_exception(e), f"Lỗi khi chạy '{command}': {e}") from e
        if IOS_ERROR_RX.search(out or ""):
            raise AdapterError("COMMAND", f"Thiết bị từ chối lệnh '{command}': {out.strip()[:120]}")
        return out

    def get_device_info(self):
        return parse_show_version(self.run_show("show version"))

    def get_running_config(self):
        cfg = self.run_show("show running-config", read_timeout=90)
        if len(cfg.strip()) < 20 or not re.search(r"^hostname\s+\S+", cfg, re.MULTILINE):
            raise AdapterError("COMMAND", "Cấu hình trả về rỗng hoặc không hợp lệ (thiếu 'hostname').")
        return cfg

    def test_connection(self):
        """Không bao giờ raise: luôn trả dict để API/UI hiển thị trạng thái."""
        start = time.monotonic()
        result = {"ok": False, "device": self.device.get("name"), "ip": self.device.get("ip"),
                  "error_type": None, "message": None, "latency_ms": None, "prompt": None}
        try:
            self.connect()
            result["prompt"] = self.conn.find_prompt()
            result["ok"] = True
            result["message"] = "Kết nối SSH thành công."
        except AdapterError as e:
            result.update(error_type=e.error_type, message=e.message)
        finally:
            result["latency_ms"] = int((time.monotonic() - start) * 1000)
            self.disconnect()
        return result

    # --- ghi cấu hình (chỉ gọi từ workflow đã duyệt) ---------------------
    def apply_config(self, commands, read_timeout=60):
        """Gửi danh sách lệnh cấu hình đã qua validate. Trả về dict kết quả."""
        self._require_conn()
        cmds = [c for c in (commands or []) if str(c).strip()]
        if not cmds:
            raise AdapterError("COMMAND", "Danh sách lệnh cấu hình rỗng.")
        if any(re.search(r"[\x00-\x1f?]", c) for c in cmds):
            raise AdapterError("COMMAND", "Lệnh chứa ký tự điều khiển hoặc '?'.")
        try:
            out = self.conn.send_config_set(cmds, read_timeout=read_timeout)
        except Exception as e:  # noqa: BLE001
            raise AdapterError(classify_exception(e), f"Lỗi khi gửi cấu hình: {e}") from e
        errors = [m.group(0) for m in re.finditer(r"^%.*$", out or "", re.MULTILINE) if IOS_ERROR_RX.match(m.group(0))]
        return {"ok": not errors, "output": out, "errors": errors}

    def save_config(self):
        self._require_conn()
        try:
            return self.conn.save_config()
        except Exception as e:  # noqa: BLE001
            raise AdapterError(classify_exception(e), f"Lỗi khi lưu cấu hình: {e}") from e
