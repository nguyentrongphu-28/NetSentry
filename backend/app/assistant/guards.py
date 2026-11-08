"""Lớp bảo vệ xác định (deterministic): chuẩn hóa, phát hiện injection, che bí mật, allowlist lệnh."""
import re
import unicodedata


def fold(text: str) -> str:
    """Bỏ dấu tiếng Việt + lowercase (người dùng hay gõ không dấu)."""
    t = unicodedata.normalize("NFD", text or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("đ", "d").replace("Đ", "D").lower()


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


# ----------------------------------------------------------------- injection
_INJECTION = [
    ("override_instructions", r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+|your\s+)?(previous\s+|prior\s+|above\s+|earlier\s+|system\s+)?(instructions?|rules?|prompts?)"),
    ("override_vi", r"(bo qua|quen|huy|vo hieu hoa)\s+(tat ca\s+|moi\s+|het\s+)?(cac\s+)?(huong dan|chi dan|quy tac|luat|gioi han)"),
    ("role_change", r"(you are now|act as|pretend to be|developer mode|jailbreak|\bdan mode|ban bay gio la|hay dong vai)"),
    ("reveal_prompt", r"((reveal|show|print|repeat|leak)\s+(me\s+)?(your\s+|the\s+)?(system\s+)?(prompt|instructions))|((in ra|hien thi|tiet lo)\s+(system\s+)?prompt)"),
    ("direct_exec", r"(\bssh\s+(vao|into|to)\b|\btelnet\s+(vao|to)\b|\brun\s+(this\s+|the\s+)?(command|cli)\b|\bexecute\s+(this|the|command|directly)\b|chay lenh|thuc thi (ngay|truc tiep|lenh)|ap dung ngay|cau hinh luon|tu dong (ap dung|thuc thi))"),
    ("bypass_approval", r"(skip|bypass|without|no need for|khong can|bo qua|mien)\s+(the\s+)?(approval|approve|phe duyet|xac nhan|allowlist|validation|kiem tra)"),
    ("disable_controls", r"(disable|turn off|tat)\s+(the\s+)?(allowlist|guard|validation|rbac|audit|logging|kiem soat|bao ve)"),
    ("dangerous_cmd", r"(\bwrite\s+erase\b|\berase\s+(startup|nvram|flash)|\breload\b|\bdelete\s+flash|\bformat\s+flash|crypto\s+key\s+zeroize|\bno\s+username\b)"),
    ("reveal_secret", r"((cho (toi )?xem|hien thi|show|reveal|print)\s+(mat khau|password|enable secret|community|secret))|((mat khau|password|secret|community)\s+(that|thuc te|goc|plaintext|plain text|cleartext|real|actual))"),
]
_INJECTION_RE = [(n, re.compile(p)) for n, p in _INJECTION]


def detect_injection(text: str) -> list:
    """Trả về danh sách tên chữ ký khớp. Heuristic: lớp phụ, KHÔNG phải biện pháp chính."""
    f = fold(text)
    return [n for n, rx in _INJECTION_RE if rx.search(f)]


# ------------------------------------------------------------------- secrets
_PH = r"(?!(?:\d\s+)?<)"          # cho phép placeholder <...> và <REDACTED>
_SECRETS = [
    ("enable_secret", re.compile(r"(?i)\benable\s+(?:password|secret)\s+" + _PH + r"\S+")),
    ("user_secret", re.compile(r"(?i)\busername\s+\S+\s+(?:\S+\s+){0,3}?(?:password|secret)\s+" + _PH + r"\S+")),
    ("line_password", re.compile(r"(?im)^\s*password\s+" + _PH + r"\S+")),
    ("snmp_community", re.compile(r"(?i)\bsnmp-server\s+community\s+(?!<)(?!(?:public|private)\b)\S+")),
    ("key_string", re.compile(r"(?i)\b(?:key-string|pre-shared-key)\s+(?:\d\s+)?" + _PH + r"[A-Za-z0-9+/=]{8,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("api_key", re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{16,}|AIza[0-9A-Za-z_\-]{20,})")),
    ("kv_token", re.compile(r"(?i)\b(?:api[_-]?key|token|passwd)\s*[:=]\s*\S{8,}")),
    ("crypt_hash", re.compile(r"\$[1-9]\$[./0-9A-Za-z]{1,16}\$[./0-9A-Za-z]{8,}")),
]


# Trong VĂN XUÔI (answer/why/impact/quote) cụm "enable password cũ" là câu bình thường, nên chỉ coi là bí mật khi
# trông giống bí mật: có mã loại + token (secret 5 xxxx), hoặc token có chữ số/ký tự đặc biệt. Mật khẩu chữ thường thuần
# ("enable secret hunter") trong văn xuôi KHÔNG bị bắt — được bù bằng việc LLM không bao giờ nhận bí mật thật (scrub đầu vào).
_PROSE_SECRETS = [
    ("typed_secret", re.compile(r"(?i)\b(?:enable\s+(?:password|secret)|password|secret)\s+\d\s+(?!<)\S{4,}")),
    ("weak_literal", re.compile(r"(?i)\b(?:enable\s+(?:password|secret)|username\s+\S+\s+(?:\S+\s+){0,3}?(?:password|secret))\s+(?!(?:\d\s+)?<)(?=\S*[\d$!@#%^&*])\S{6,}")),
] + [x for x in _SECRETS if x[0] in {"snmp_community", "key_string", "private_key", "api_key", "kv_token", "crypt_hash"}]


def find_secrets(text: str, prose: bool = False) -> list:
    return [n for n, rx in (_PROSE_SECRETS if prose else _SECRETS) if rx.search(text or "")]


def scrub_secrets(text: str) -> str:
    """Thay phần bí mật bằng <REDACTED> (lớp phòng thủ thứ hai; snapshot đã được sanitizer của A che)."""
    out = text or ""
    for _, rx in _SECRETS:
        out = rx.sub("<REDACTED>", out)
    return out


# ------------------------------------------------------------ command gating
# Chỉ những dòng này mới được xuất hiện trong manual_steps. Mọi thứ khác bị từ chối.
_ALLOWED = [re.compile(p) for p in [
    r"^line (con 0|vty \d+( \d+)?)$",
    r"^transport input ssh$",
    r"^exec-timeout (?!0 0$)\d+( \d+)?$",
    r"^logging synchronous$",
    r"^access-class \S+ in$",
    r"^service password-encryption$",
    r"^no ip http server$",
    r"^ip ssh version 2$",
    r"^no ip source-route$",
    r"^no ip domain[- ]lookup$",
    r"^no ip proxy-arp$",
    r"^interface (fastethernet|gigabitethernet|vlan)\s?\d+(/\d+){0,2}$",
    r"^enable secret <[^>\s]+>$",              # bí mật chỉ được là placeholder
    r"^no enable password$",
    r"^no snmp-server community (public|private)$",
    r"^ip access-list standard [\w-]+$",
    r"^permit (<[^>\s]+>|\d{1,3}(\.\d{1,3}){3}) (<[^>\s]+>|\d{1,3}(\.\d{1,3}){3})$",
    r"^banner (motd|login) \^c$",
    r"^\^c$",
    # tác vụ VLAN (khớp task_template của A)
    r"^vlan \d{1,4}$",
    r"^name [\w-]{1,32}$",
    r"^exit$",
    r"^switchport mode access$",
    r"^switchport access vlan \d{1,4}$",
    r"^no shutdown$",
]]

# Lệnh nguy hiểm: một DÒNG bắt đầu bằng chúng (hoặc "chạy/run: <lệnh>") bị chặn, kể cả trong văn xuôi.
# Cố ý hẹp: các từ thường như "telnet", "ssh", "copy", "format" đứng một mình KHÔNG bị coi là lệnh trong văn xuôi
# (vd. câu "Telnet gửi dữ liệu không mã hóa"). Với manual_steps thì allowlist ở trên mới là chốt chặn chính.
_DANGEROUS_START = (r"(?:reload\b|write\s+(?:erase|mem\w*)\b|erase\s+\S+|delete\s+\S+|format\s+\S+|copy\s+\S+\s+\S+|"
                    r"configure\s+replace\b|crypto\s+key\s+\S+|no\s+username\b|username\s+\S+\s+(?:privilege|password|secret)\b|"
                    r"no\s+enable\s+secret\b|no\s+aaa\b|tclsh\b|event\s+manager\b|do\s+(?:reload|write|erase|copy)\b|shutdown\s*$)")
_DANGEROUS_LINE = re.compile(r"^\s*" + _DANGEROUS_START)
_DANGEROUS_RUN = re.compile(r"\b(run|execute|apply|chay|thuc thi|ap dung)\s*:?\s*[`'\"]?" + _DANGEROUS_START)

URL_OR_RENDER = re.compile(r"(https?://|ftp://|www\.|!\[|\]\(|<img|<script|<iframe|<a\s|javascript:|data:text)", re.I)


def find_dangerous_in_prose(text: str) -> list:
    hits = []
    for line in (text or "").splitlines() or [""]:
        f = fold(line)
        if _DANGEROUS_LINE.match(f) or _DANGEROUS_RUN.search(f):
            hits.append(collapse_ws(line)[:60])
    return hits


def check_command_line(line: str, extra_allowed: frozenset = frozenset()):
    """(ok, reason). Dòng trong ngoặc đơn = ghi chú, chỉ bị kiểm tra bí mật/nguy hiểm."""
    raw = collapse_ws(line)
    if not raw:
        return False, "empty_line"
    if len(raw) > 200:
        return False, "line_too_long"
    if find_secrets(raw):
        return False, "contains_secret"
    f = fold(raw)
    if raw.startswith("(") and raw.endswith(")"):
        return (False, "dangerous_in_note") if find_dangerous_in_prose(raw[1:-1]) else (True, "note")
    if _DANGEROUS_LINE.match(f):
        return False, "dangerous_command"
    if f in extra_allowed:
        return True, "remediation_line"
    if any(rx.match(f) for rx in _ALLOWED):
        return True, "allowlist"
    return False, "not_in_allowlist"
