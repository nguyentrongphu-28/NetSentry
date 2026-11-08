# scripts/test_week3.py  --  Tuần 3: inventory, snapshot, sanitizer, adapter
import json
import os
import stat
import tempfile

from tests import fakes
from app.devices import network_adapter
from app.devices.inventory_loader import load_inventory
from app.devices.network_adapter import AdapterError, NetworkAdapter, parse_show_version
from app.core.paths import INVENTORY_PATH
from app.devices.sanitizer import sanitize_config, sanitize_config_with_stats
from app.devices.snapshot_collector import collect_snapshot, list_snapshots, load_snapshot_text, save_snapshot
from tests.testing_utils import run_tests

DEV = {"id": "dev_switch_01", "name": "Switch-LAB", "ip": "172.16.3.122", "device_type": "cisco_ios", "role": "switch"}
CREDS = {"username": "u", "password": "p"}


def _adapter_factory(factory):
    return lambda device, **kw: NetworkAdapter(device, connection_factory=factory, **CREDS)


# ---------------- inventory ----------------
def test_inventory_loads_real_file():
    devs = load_inventory(INVENTORY_PATH, verbose=False)
    assert len(devs) >= 2
    assert {d["role"] for d in devs} >= {"router", "switch"}


def test_sanitizer_masks_ntp_key_not_algorithm():
    """Hồi quy: 'ntp authentication-key 1 md5 KEY' từng che nhầm 'md5' và để lộ KEY."""
    raw = "ntp authentication-key 1 md5 NtpKey123\nntp authentication-key 2 md5 7 0A0B0C\nwpa-psk ascii 0 WifiPass123\n"
    out = sanitize_config(raw)
    for leaked in ("NtpKey123", "0A0B0C", "WifiPass123"):
        assert leaked not in out, leaked
    assert "md5" in out
    assert sanitize_config(out) == out        # idempotent


def test_run_show_blocks_newline_injection():
    """Hồi quy: 'show version\\nreload' từng lọt cổng chỉ-đọc vì regex dùng \\s."""
    ad = NetworkAdapter(DEV, connection_factory=fakes.make_factory(fakes.standard_outputs()), **CREDS).connect()
    for bad in ["show version\nreload", "show version\r\nconfigure terminal", "show version\twrite erase",
                "show running-config | include snmp\nreload", "show version; reload", "configure terminal", ""]:
        try:
            ad.run_show(bad)
        except AdapterError as e:
            assert e.error_type == "COMMAND", bad
        else:
            raise AssertionError(f"lệnh không được chặn: {bad!r}")
    assert ad.run_show("show version")
    ad.disconnect()


def test_inventory_rejects_bad_entries():
    bad = [
        {"id": "a", "name": "ok", "ip": "10.0.0.1", "device_type": "cisco_ios"},
        {"id": "b", "name": "badip", "ip": "999.1.1.1", "device_type": "cisco_ios"},
        {"id": "c", "ip": "10.0.0.3", "device_type": "cisco_ios"},                         # thiếu name
        {"id": "a", "name": "dup", "ip": "10.0.0.4", "device_type": "cisco_ios"},          # trùng id
        {"id": "e", "name": "badrole", "ip": "10.0.0.5", "device_type": "cisco_ios", "role": "firewall"},
    ]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "inv.json")
        json.dump(bad, open(p, "w"))
        devs = load_inventory(p, verbose=False)
    assert [x["id"] for x in devs] == ["a"]


def test_inventory_missing_and_corrupt_file():
    with tempfile.TemporaryDirectory() as d:
        assert load_inventory(os.path.join(d, "nope.json"), verbose=False) == []
        p = os.path.join(d, "bad.json")
        open(p, "w").write("{ not json")
        assert load_inventory(p, verbose=False) == []


# ---------------- sanitizer ----------------
def test_sanitizer_no_leaks():
    raw = """enable secret cisco
enable password 7 0822455D0A16
username admin privilege 15 secret 5 $1$abc$xyzHASH
username bob password 7 104D000A0618
line vty 0 4
 password 7 060506324F41
snmp-server community PUBLIC123 RO
snmp-server host 10.0.0.1 version 2c HOSTSTR
tacacs-server key 7 02050D480809
ip ospf message-digest-key 1 md5 7 0822455D
crypto isakmp key MYKEY address 1.1.1.1
"""
    out = sanitize_config(raw)
    for leaked in ("cisco", "0822455D0A16", "xyzHASH", "104D000A0618", "060506324F41", "PUBLIC123",
                   "HOSTSTR", "02050D480809", "0822455D", "MYKEY"):
        assert leaked not in out, f"Bị lọt: {leaked}"


def test_sanitizer_keeps_evidence_and_is_idempotent():
    raw = "enable secret 5 $1$x$y\nusername a privilege 15 secret 9 HASH\nsnmp-server community public RO\nservice password-encryption\nusername n nopassword\n"
    out, n = sanitize_config_with_stats(raw)
    assert "enable secret 5 <REDACTED>" in out          # giữ loại mã hóa (bằng chứng)
    assert "secret 9 <REDACTED>" in out
    assert "snmp-server community public RO" in out     # community mặc định là bằng chứng, không phải bí mật
    assert "service password-encryption" in out and "username n nopassword" in out
    assert n == 2
    assert sanitize_config(out) == out
    assert sanitize_config("") == "" and sanitize_config(None) == ""


# ---------------- adapter ----------------
def test_parse_show_version():
    sw = parse_show_version(fakes.SHOW_VERSION)
    assert sw["hostname"] == "Switch-LAB" and sw["model"] == "WS-C2960-24TT-L"
    assert sw["ios_version"] == "15.0(2)SE11" and sw["serial"] == "FOC1234X0AB"
    rt = parse_show_version("Cisco IOS Software, C1900 Software, Version 15.4(3)M2, RELEASE SOFTWARE\n"
                            "Router-LAB uptime is 1 week\nCisco CISCO1941/K9 (revision 1.0) with 491520K/32768K bytes of memory.\n"
                            "Processor board ID FTX1234ABCD\n")
    assert rt["model"] == "CISCO1941/K9" and rt["ios_version"] == "15.4(3)M2" and rt["serial"] == "FTX1234ABCD"


def test_adapter_is_read_only():
    ad = NetworkAdapter(DEV, connection_factory=fakes.make_factory(fakes.standard_outputs()), **CREDS).connect()
    for cmd in ("configure terminal", "show run; reload", "reload", "show version\nreload", "write erase", ""):
        try:
            ad.run_show(cmd)
            assert False, f"Lẽ ra phải chặn: {cmd!r}"
        except AdapterError as e:
            assert e.error_type == "COMMAND"
    assert "Version" in ad.run_show("show version")
    ad.disconnect()


def test_adapter_error_classification():
    cases = [(fakes.NetmikoTimeoutException("timed out"), "TIMEOUT"),
             (fakes.NetmikoAuthenticationException("bad creds"), "AUTH"),
             (OSError("No route to host"), "CONNECTION"),
             (ValueError("lạ"), "UNKNOWN")]
    for exc, expected in cases:
        res = NetworkAdapter(DEV, connection_factory=fakes.make_factory(exc=exc), **CREDS).test_connection()
        assert res["ok"] is False and res["error_type"] == expected, (exc, res)
        assert res["latency_ms"] is not None


def test_adapter_test_connection_ok_and_passes_timeouts():
    f = fakes.make_factory(fakes.standard_outputs())
    res = NetworkAdapter(DEV, connection_factory=f, timeout=7, **CREDS).test_connection()
    assert res["ok"] is True and res["prompt"] == "Switch-LAB#"
    assert f.holder["params"]["conn_timeout"] == 7 and f.holder["params"]["host"] == DEV["ip"]
    assert f.holder["conn"].disconnected is True


def test_adapter_missing_credentials():
    saved_env = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("NETSENTRY_")}
    saved_loader = network_adapter.load_env
    network_adapter.load_env = lambda path=None: None
    try:
        res = NetworkAdapter(DEV, connection_factory=fakes.make_factory({})).test_connection()
        assert res["ok"] is False and res["error_type"] == "CONFIG"
    finally:
        network_adapter.load_env = saved_loader
        os.environ.update(saved_env)


def test_adapter_rejects_empty_running_config():
    out = fakes.standard_outputs()
    out["show running-config"] = "  \n"
    ad = NetworkAdapter(DEV, connection_factory=fakes.make_factory(out), **CREDS).connect()
    try:
        ad.get_running_config()
        assert False
    except AdapterError as e:
        assert e.error_type == "COMMAND"


# ---------------- snapshot ----------------
def test_snapshot_saved_sanitized_with_metadata():
    with tempfile.TemporaryDirectory() as d:
        meta = save_snapshot(DEV, fakes.RAW_CONFIG, info=parse_show_version(fakes.SHOW_VERSION), out_dir=d)
        text = open(os.path.join(d, meta["file"]), encoding="utf-8").read()
        for secret in ("FAKEHASHENABLE", "FAKEHASHUSER", "060506324F41", "S3cretCommunity"):
            assert secret not in text, secret
        assert "enable secret 5 <REDACTED>" in text and "snmp-server community public RO" in text
        assert meta["redactions"] == 4 and meta["model"] == "WS-C2960-24TT-L" and meta["ios_version"] == "15.0(2)SE11"
        assert meta["device_id"] == "dev_switch_01" and meta["collected_at"].endswith("+00:00")
        assert os.path.exists(os.path.join(d, meta["snapshot_id"] + ".meta.json"))
        if os.name == "posix":
            assert stat.S_IMODE(os.stat(os.path.join(d, meta["file"])).st_mode) == 0o600


def test_snapshot_collect_success():
    with tempfile.TemporaryDirectory() as d:
        f = fakes.make_factory(fakes.standard_outputs())
        res = collect_snapshot(DEV, adapter_factory=_adapter_factory(f), out_dir=d)
        assert res["ok"] is True and res["snapshot"]["model"] == "WS-C2960-24TT-L"
        assert "FAKEHASHENABLE" not in load_snapshot_text(res["snapshot"], out_dir=d)
        assert f.holder["conn"].disconnected is True


def test_snapshot_collect_failures_write_nothing():
    for exc, expected in [(fakes.NetmikoTimeoutException("t"), "TIMEOUT"), (fakes.NetmikoAuthenticationException("a"), "AUTH")]:
        with tempfile.TemporaryDirectory() as d:
            res = collect_snapshot(DEV, adapter_factory=_adapter_factory(fakes.make_factory(exc=exc)), out_dir=d)
            assert res["ok"] is False and res["error_type"] == expected
            assert os.listdir(d) == []
    with tempfile.TemporaryDirectory() as d:        # thiết bị trả cấu hình rỗng
        out = fakes.standard_outputs()
        out["show running-config"] = ""
        res = collect_snapshot(DEV, adapter_factory=_adapter_factory(fakes.make_factory(out)), out_dir=d)
        assert res["ok"] is False and os.listdir(d) == []


def test_snapshot_unique_names_and_listing():
    with tempfile.TemporaryDirectory() as d:
        a = save_snapshot(DEV, fakes.RAW_CONFIG, out_dir=d)
        b = save_snapshot(DEV, fakes.RAW_CONFIG, out_dir=d)
        assert a["file"] != b["file"]
        metas = list_snapshots("Switch-LAB", out_dir=d)
        assert len(metas) == 2 and list_snapshots("Router-LAB", out_dir=d) == []
        assert a["content_sha256"] == b["content_sha256"]


def test_snapshot_dir_writable():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "probe.txt")
        open(p, "w").write("x")
        assert os.path.exists(p)


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_tests(globals(), "TUẦN 3 - inventory / snapshot / sanitizer / adapter") else 1)
