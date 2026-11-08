# scripts/sanitizer.py
"""Che các thông tin nhạy cảm trong cấu hình Cisco TRƯỚC khi lưu/hiển thị/gửi AI.

Nguyên tắc:
- Giữ lại "loại mã hóa" (0/5/7/8/9) vì đó là bằng chứng cho audit (vd: type 7 yếu).
- SNMP community 'public'/'private' được GIỮ NGUYÊN vì đó chính là bằng chứng của
  rule SEC-012 (đây là giá trị mặc định công khai, không phải bí mật).
- Hàm idempotent: chạy lại nhiều lần không đổi kết quả.
"""
import re

REDACTED = "<REDACTED>"
WEAK_SNMP = {"public", "private"}
_F = re.IGNORECASE | re.MULTILINE


def _secret_sub(m, counter):
    value = m.group("v")
    if value.startswith("<REDACTED"):
        return m.group(0)
    counter[0] += 1
    t = f"{m.group('t')} " if m.groupdict().get("t") else ""
    return f"{m.group('pre')}{t}{REDACTED}"


# Mỗi pattern có 3 nhóm: pre (giữ lại), t (loại mã hóa, tùy chọn), v (giá trị bị che)
_SECRET_PATTERNS = [
    # ntp authentication-key N md5|sha1 [type] KEY  (phải đứng TRƯỚC mẫu authentication-key chung, nếu không
    # mẫu chung coi 'md5' là giá trị và để lộ khóa thật)
    re.compile(r"^(?P<pre>[ \t]*ntp[ \t]+authentication-key[ \t]+\d+[ \t]+(?:md5|sha1|sha2|cmac-aes-128)[ \t]+)(?:(?P<t>\d+)[ \t]+)?(?P<v>\S+)", _F),
    # wpa-psk ascii [type] KEY
    re.compile(r"^(?P<pre>[ \t]*[^\n]*?\bwpa-psk[ \t]+(?:ascii|hex)[ \t]+)(?:(?P<t>\d+)[ \t]+)?(?P<v>\S+)", _F),
    # enable secret/password, username ... secret/password, line password, ppp chap password ...
    re.compile(r"^(?P<pre>[ \t]*[^\n]*?\b(?:password|secret)[ \t]+(?:level[ \t]+\d+[ \t]+)?)(?:(?P<t>\d+)[ \t]+)?(?P<v>\S+)", _F),
    # authentication-key / key-string (OSPF, EIGRP, RIP, key chain)
    re.compile(r"^(?!ntp[ \t]+authentication-key)(?P<pre>[ \t]*[^\n]*?\b(?:authentication-key|key-string)[ \t]+)(?:(?P<t>\d+)[ \t]+)?(?P<v>\S+)", _F),
    # ip ospf message-digest-key N md5 [type] KEY
    re.compile(r"^(?P<pre>[ \t]*[^\n]*?\bmessage-digest-key[ \t]+\d+[ \t]+md5[ \t]+)(?:(?P<t>\d+)[ \t]+)?(?P<v>\S+)", _F),
    # tacacs-server / radius-server ... key [type] KEY
    re.compile(r"^(?P<pre>[ \t]*(?:tacacs-server|radius-server)\b[^\n]*?\bkey[ \t]+)(?:(?P<t>\d+)[ \t]+)?(?P<v>\S+)", _F),
    # 'key 7 HASH' trong khối 'tacacs server X' / 'radius server X'
    re.compile(r"^(?P<pre>[ \t]+key[ \t]+)(?P<t>\d+)[ \t]+(?P<v>\S+)", _F),
    # 'key PLAINTEXT' (bắt đầu bằng chữ cái, để không đụng 'key 1' của key chain)
    re.compile(r"^(?P<pre>[ \t]+key[ \t]+)(?P<t>)(?P<v>[A-Za-z]\S*)", _F),
    # crypto isakmp key / pre-shared-key
    re.compile(r"^(?P<pre>[ \t]*[^\n]*?\b(?:isakmp[ \t]+key|pre-shared-key[ \t]+(?:local[ \t]+|remote[ \t]+)?)[ \t]*)(?:(?P<t>\d+)[ \t]+)?(?P<v>\S+)", _F),
    # snmp-server user ... auth md5 X priv aes 128 Y
    re.compile(r"(?P<pre>\bauth[ \t]+(?:md5|sha)[ \t]+)(?P<t>)(?P<v>\S+)", _F),
    re.compile(r"(?P<pre>\bpriv[ \t]+(?:aes[ \t]+\d+|des|3des)[ \t]+)(?P<t>)(?P<v>\S+)", _F),
]

_SNMP_COMMUNITY = re.compile(r"^(?P<pre>[ \t]*snmp-server[ \t]+community[ \t]+)(?P<v>\S+)", _F)
_SNMP_HOST = re.compile(
    r"^(?P<pre>[ \t]*snmp-server[ \t]+host[ \t]+\S+[ \t]+(?:(?:informs|traps)[ \t]+)?"
    r"(?:version[ \t]+\S+[ \t]+(?:(?:priv|auth|noauth)[ \t]+)?)?)(?P<v>\S+)", _F)


def _snmp_sub(counter):
    def repl(m):
        v = m.group("v")
        if v.startswith("<REDACTED") or v.lower() in WEAK_SNMP:
            return m.group(0)
        counter[0] += 1
        return f"{m.group('pre')}{REDACTED}"
    return repl


def sanitize_config_with_stats(raw_config):
    """Trả về (cấu hình đã làm sạch, số vị trí đã che)."""
    if not raw_config:
        return "", 0
    counter = [0]
    text = raw_config
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: _secret_sub(m, counter), text)
    text = _SNMP_COMMUNITY.sub(_snmp_sub(counter), text)
    text = _SNMP_HOST.sub(_snmp_sub(counter), text)
    return text, counter[0]


def sanitize_config(raw_config):
    """Giữ tên hàm cũ để tương thích: chỉ trả về chuỗi đã làm sạch."""
    return sanitize_config_with_stats(raw_config)[0]
