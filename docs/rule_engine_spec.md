# NetSentry – Đặc tả Rule Engine cho Antigravity

> Cách dùng: lưu file này vào `docs/rule_engine_spec.md` trong repo, mở Antigravity ở chế độ **Planning**, gửi prompt: *"Đọc @docs/rule_engine_spec.md và thực hiện đúng từng bước ở mục 8. Hãy đưa plan trước, đợi tôi duyệt rồi mới code."*
> Quy ước ngôn ngữ: giải thích bằng tiếng Việt; **tên file, class, hàm, docstring, comment và nội dung finding (title/rationale/remediation) viết bằng tiếng Anh.**

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư Python senior. Hãy xây **Rule Engine** cho NetSentry (kiểm toán cấu hình Cisco IOS) trong thư mục `backend/`, theo đúng đặc tả bên dưới.

Quy tắc làm việc bắt buộc:

1. Làm theo đúng thứ tự các bước ở **mục 8**. Sau mỗi bước chạy `pytest -q` (từ thư mục `backend/`) và chỉ sang bước tiếp theo khi test xanh.
2. Không thêm tính năng ngoài phạm vi (mục 1). Nếu thấy cần thay đổi đặc tả, **dừng lại và hỏi**, không tự quyết.
3. Không sửa `app/connectors/ssh_connector.py` (hoặc file SSH hiện có) trong giai đoạn này.
4. Mọi thư mục Python phải có `__init__.py`. Dùng Python 3.11+, type hints đầy đủ, `from __future__ import annotations` khi cần.
5. Code phải **deterministic**: cùng cấu hình đầu vào cho cùng kết quả; không gọi mạng, không đọc file ngoài tham số, không dùng `datetime.now()` bên trong rule.

---

## 1. Phạm vi

**Làm trong giai đoạn này**

- Domain: `Finding`, `Severity`, `FindingStatus`, `ParsedConfig`, `ConfigBlock`, interface `AuditRule`, `ConfigParser`.
- Parser cấu hình Cisco IOS (text → `ParsedConfig`).
- Tiện ích che bí mật (`redaction`).
- 8 rule audit (mục 5), `BaseRule`, `registry`, `RuleEngine`.
- Fixtures cấu hình mẫu + unit tests.
- Script CLI chạy engine trên một file cấu hình.

**KHÔNG làm**

- Không kết nối thiết bị, không import `netmiko`/`paramiko` trong `domain/` và `rules/`.
- Không làm API/FastAPI route, database/repository, AI/Ollama, remediation thực thi, frontend.
- Rule **không bao giờ** thực thi lệnh; trường `remediation` chỉ là văn bản hướng dẫn.

---

## 2. Ràng buộc kiến trúc (dependency rule)

- `app/domain/` **chỉ** dùng thư viện chuẩn Python. Cấm import: `fastapi`, `pydantic`, `sqlalchemy`, `netmiko`, `paramiko`, `ollama`, `requests`.
- `app/rules/` chỉ import từ `app.domain`, `app.core.redaction` và thư viện chuẩn. Cấm import các thư viện hạ tầng ở trên.
- Pattern: **Strategy** (mỗi rule một class cùng interface `AuditRule`), **Dependency Injection** (engine nhận danh sách rule + parser + clock từ bên ngoài).
- Phải có một test tự động (dùng `ast`) quét `app/domain` và `app/rules` để đảm bảo không vi phạm danh sách import bị cấm.

---

## 3. Cây thư mục cần tạo (chỉ liệt kê file thuộc giai đoạn này)

```
backend/
  pytest.ini                      # pythonpath = .   testpaths = tests
  requirements-dev.txt            # pytest (thêm nếu chưa có)
  app/
    __init__.py
    core/
      __init__.py
      redaction.py
    domain/
      __init__.py
      entities/
        __init__.py
        finding.py                # Severity, FindingStatus, Finding
        parsed_config.py          # ConfigBlock, ParsedConfig
      interfaces/
        __init__.py
        audit_rule.py             # AuditRule (ABC)
        config_parser.py          # ConfigParser (ABC)
    rules/
      __init__.py
      ios_config_parser.py        # IosConfigParser(ConfigParser)
      base_rule.py              # BaseRule(AuditRule)
      telnet_rule.py            # NET-001
      ssh_rule.py               # NET-002
      password_rule.py          # NET-003, NET-004
      vty_timeout_rule.py       # NET-005
      vty_acl_rule.py           # NET-006
      snmp_rule.py              # NET-007
      http_server_rule.py       # NET-008
      registry.py               # get_default_rules(), build_default_engine()
      engine.py                 # RuleEngine
  tests/
    __init__.py
    fixtures/
      configs/
        ios_secure.cfg
        ios_insecure.cfg
        ios_minimal.cfg
        ios_banner_trap.cfg
    unit/
      __init__.py
      test_architecture_imports.py
      test_redaction.py
      test_ios_config_parser.py
      test_engine.py
      rules/
        __init__.py
        test_telnet_rule.py
        test_ssh_rule.py
        test_password_rules.py
        test_vty_timeout_rule.py
        test_vty_acl_rule.py
        test_snmp_rule.py
        test_http_server_rule.py
scripts/
  run_rules_on_file.py
data/
  raw_configs/                    # cấu hình thật, phải nằm trong .gitignore
```

Thêm vào `.gitignore` (nếu chưa có): `data/raw_configs/`, `*.env`, `.env`.

---

## 4. Đặc tả từng file

### 4.1 `domain/entities/finding.py`

```python
class Severity(StrEnum):
    INFO = "INFO"; LOW = "LOW"; MEDIUM = "MEDIUM"; HIGH = "HIGH"; CRITICAL = "CRITICAL"

class FindingStatus(StrEnum):
    PASS = "PASS"        # rule đã chạy, cấu hình đạt
    FAIL = "FAIL"        # có bằng chứng vi phạm
    UNKNOWN = "UNKNOWN"  # không đủ dữ liệu / không thể kết luận

@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    title: str
    severity: Severity          # mức độ nếu FAIL (PASS/UNKNOWN vẫn giữ mức của rule)
    status: FindingStatus
    evidence: tuple[str, ...]   # các dòng cấu hình ĐÃ che bí mật
    rationale: str
    remediation: str            # chỉ là văn bản hướng dẫn, KHÔNG thực thi
    verification: str           # cách kiểm tra lại sau khi sửa
    device_id: str | None = None
    checked_at: datetime | None = None   # engine điền, rule không điền

    def to_dict(self) -> dict[str, Any]: ...   # severity/status thành str, checked_at thành ISO-8601
```

Quy ước: **mỗi lần chạy, mỗi rule trả về đúng 1 `Finding`** (PASS, FAIL hoặc UNKNOWN). Việc ghi cả PASS giúp có audit trail ("rule đã được đánh giá") và tính precision/recall sau này; dashboard sẽ lọc FAIL.

### 4.2 `domain/entities/parsed_config.py`

```python
@dataclass(frozen=True, slots=True)
class ConfigBlock:
    header: str                       # vd "line vty 0 4" (đã strip)
    children: tuple[str, ...]         # các dòng con đã strip, gom phẳng mọi mức thụt lề

    def child_starting_with(self, prefix: str) -> list[str]: ...   # so khớp không phân biệt hoa/thường
    def has_child(self, prefix: str) -> bool: ...

@dataclass(frozen=True, slots=True)
class ParsedConfig:
    global_lines: tuple[str, ...]     # dòng cấp 0 không có con
    blocks: tuple[ConfigBlock, ...]   # dòng cấp 0 có con (interface, line vty, router ...)

    def global_starting_with(self, prefix: str) -> list[str]: ...
    def has_global(self, exact: str) -> bool: ...
    def blocks_starting_with(self, prefix: str) -> list[ConfigBlock]: ...
```

Mọi so khớp prefix/exact **không phân biệt hoa/thường**, nhưng giá trị trả về giữ nguyên chữ gốc.

### 4.3 `domain/interfaces/audit_rule.py` và `config_parser.py`

```python
class AuditRule(ABC):
    rule_id: str
    title: str
    severity: Severity
    platforms: tuple[str, ...]        # vd ("cisco_ios",)

    @abstractmethod
    def check(self, config: ParsedConfig) -> list[Finding]: ...

    def applies_to(self, platform: str) -> bool:
        return platform in self.platforms

class ConfigParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> ParsedConfig: ...
```

### 4.4 `rules/ios_config_parser.py` – `IosConfigParser`

Yêu cầu:

- Chuẩn hóa `\r\n` → `\n`. Bỏ dòng rỗng, dòng chỉ có `!`, dòng `Building configuration...`, `Current configuration : ... bytes`, `Using ... out of ... bytes`, `end`.
- Dòng cấp 0 = không thụt lề. Các dòng thụt lề ngay sau đó là `children` của dòng cấp 0 gần nhất. Dòng cấp 0 không có con → `global_lines`; có con → `ConfigBlock`.
- **Banner (bắt buộc xử lý)**: dòng bắt đầu `banner <loại> <delim>` (delim là ký tự đầu tiên sau loại, vd `^C` hoặc `#`) mở một vùng văn bản tự do. Bỏ qua **toàn bộ** nội dung cho tới dòng chứa delim đóng (nếu delim đóng nằm ngay trên cùng dòng mở thì banner chỉ một dòng). Không đưa nội dung banner vào `global_lines`/`blocks`. Lý do: nội dung banner có thể chứa chuỗi giống lệnh (vd `transport input telnet`) gây false positive.
- Không raise exception với đầu vào rỗng hoặc lạ; trả về `ParsedConfig` rỗng.

### 4.5 `core/redaction.py`

```python
REDACTED = "<REDACTED>"
def redact_line(line: str) -> str: ...
```

`redact_line` thay **giá trị bí mật** bằng `<REDACTED>` nhưng giữ lại phần còn lại để làm bằng chứng. Phải xử lý (không phân biệt hoa/thường):

| Dòng gốc | Kết quả mong muốn |
|---|---|
| `enable password 0 MyPass1` | `enable password 0 <REDACTED>` |
| `enable password MyPass1` | `enable password <REDACTED>` |
| `enable secret 5 $1$abc$xyz` | `enable secret 5 <REDACTED>` |
| `username admin privilege 15 password 0 Pass1` | `username admin privilege 15 password 0 <REDACTED>` |
| `username admin secret 9 $9$xxxx` | `username admin secret 9 <REDACTED>` |
| ` password 7 0822455D0A16` (trong line) | ` password 7 <REDACTED>` |
| `snmp-server community public RO` | `snmp-server community <REDACTED> RO` |
| `snmp-server community s3cr3t RW 10` | `snmp-server community <REDACTED> RW 10` |
| `... key 7 ...`, `... key <chuỗi> ...` (tacacs/radius) | giá trị sau `key [type]` → `<REDACTED>` |
| `snmp-server host 1.2.3.4 version 2c secretstr` | chuỗi community → `<REDACTED>` |

Hàm phải idempotent (gọi 2 lần không đổi kết quả) và không bao giờ raise.

### 4.6 `rules/base_rule.py` – `BaseRule(AuditRule)`

Cung cấp helper để mọi rule dựng finding thống nhất và **luôn che bí mật**:

```python
class BaseRule(AuditRule):
    description: str            # mô tả ngắn dùng cho rationale mặc định
    remediation_text: str
    verification_text: str

    def _pass(self, evidence: Iterable[str] = (), note: str | None = None) -> Finding: ...
    def _fail(self, evidence: Iterable[str], rationale: str | None = None,
              severity: Severity | None = None) -> Finding: ...
    def _unknown(self, reason: str, evidence: Iterable[str] = ()) -> Finding: ...
```

- Mọi dòng evidence đi qua `redact_line()` trong helper; rule **không được** tự tạo `Finding` mà bỏ qua helper.
- `_fail(severity=...)` cho phép ghi đè mức độ theo từng trường hợp (dùng ở NET-007).
- `check()` trả về `[finding]` (đúng 1 phần tử).

### 4.7 `rules/engine.py` – `RuleEngine`

```python
class RuleEngine:
    def __init__(self, rules: Sequence[AuditRule], parser: ConfigParser,
                 clock: Callable[[], datetime] | None = None) -> None: ...
    def run(self, config_text: str, platform: str = "cisco_ios",
            device_id: str | None = None,
            only_rule_ids: Collection[str] | None = None,
            skip_rule_ids: Collection[str] | None = None) -> list[Finding]: ...
```

Hành vi:

- `__init__` raise `ValueError` nếu có `rule_id` trùng.
- `clock` mặc định trả `datetime.now(timezone.utc)`; engine gọi 1 lần mỗi `run` rồi gắn cùng `checked_at` và `device_id` cho mọi finding (dùng `dataclasses.replace`).
- Parse cấu hình **một lần**; chỉ chạy rule có `applies_to(platform)` và thỏa `only/skip`.
- **Cô lập lỗi**: nếu một rule raise exception, bắt lại, ghi `logging.getLogger(__name__).exception(...)` (không log nội dung cấu hình) và tạo finding `UNKNOWN` với evidence `("rule execution error: <TênException>",)`. Các rule khác vẫn chạy.
- Kết quả sắp xếp theo `rule_id` tăng dần (ổn định).

### 4.8 `rules/registry.py`

```python
def get_default_rules() -> list[AuditRule]: ...      # 8 rule, theo thứ tự NET-001..NET-008
def build_default_engine(clock=None) -> RuleEngine: ... # dùng IosConfigParser
```

### 4.9 `scripts/run_rules_on_file.py`

`python scripts/run_rules_on_file.py <path.cfg> [--json] [--device-id ID]`
- Đọc file, chạy `build_default_engine()`, in bảng text (rule_id | status | severity | title) hoặc JSON (`--json`).
- Thêm `backend/` vào `sys.path` để import `app` được. Thoát với mã 0.

---

## 5. Danh sách 8 rule

Tất cả áp dụng cho `platforms = ("cisco_ios",)`. Tìm `line vty` bằng `blocks_starting_with("line vty")`.

| ID | Class (file) | Severity | FAIL khi | PASS khi | UNKNOWN khi |
|---|---|---|---|---|---|
| NET-001 | `TelnetRule` (`telnet_rule.py`) | HIGH | Có block `line vty` mà `transport input` chứa `telnet` **hoặc** `all` | Mọi block `line vty` có `transport input` và không chứa `telnet`/`all` (vd `ssh`) | Không có block `line vty`, hoặc có block nhưng thiếu dòng `transport input` (mặc định tùy phiên bản IOS) |
| NET-002 | `SshVersionRule` (`ssh_rule.py`) | MEDIUM | Có `ip ssh version 1`, hoặc không có dòng `ip ssh version 2` (chưa ép SSHv2) | Có `ip ssh version 2` | – |
| NET-003 | `PlainTextCredentialRule` (`password_rule.py`) | HIGH | Có `enable password ...`; hoặc `username ... password ...` (type 0, 7 hoặc không type); hoặc dòng `password ...` trong block `line` | Không có các dòng trên (`enable secret`, `username ... secret` là đạt) | – |
| NET-004 | `PasswordEncryptionServiceRule` (`password_rule.py`) | LOW | Không có `service password-encryption` | Có `service password-encryption` | – |
| NET-005 | `VtyExecTimeoutRule` (`vty_timeout_rule.py`) | MEDIUM | `exec-timeout 0 0`, hoặc tổng thời gian > `MAX_EXEC_TIMEOUT_SECONDS` (hằng số = 600) | Có `exec-timeout` hợp lệ ≤ ngưỡng ở mọi block vty | Không có block vty hoặc thiếu dòng `exec-timeout` (mặc định IOS 10 phút) |
| NET-006 | `VtyAccessClassRule` (`vty_acl_rule.py`) | MEDIUM | Có block vty thiếu `access-class <acl> in` | Mọi block vty có `access-class ... in` (ghi chú: nội dung ACL chưa được đánh giá) | Không có block vty |
| NET-007 | `SnmpCommunityRule` (`snmp_rule.py`) | MEDIUM (nâng lên HIGH nếu community là `RW`, hoặc tên `public`/`private`) | Có `snmp-server community ...` | Không có dòng `snmp-server community` (ghi chú: SNMPv3 chưa được đánh giá) | – |
| NET-008 | `HttpServerRule` (`http_server_rule.py`) | MEDIUM | Có dòng `ip http server` (HTTP không mã hóa) | Không có, hoặc có `no ip http server` | – |

Chi tiết bắt buộc:

- **Evidence** của FAIL phải ghi rõ vị trí, vd `line vty 0 4: transport input telnet ssh`. Với block, ghép `"<header>: <dòng con>"`. Với dòng global chỉ ghi dòng đó. Tất cả đều đi qua `redact_line`.
- **Không bao giờ** đưa community string, password, hash, key vào evidence/rationale/log (kể cả khi evidence là chuỗi lỗi).
- NET-001: `transport input none` không phải FAIL. `transport input ssh telnet` là FAIL.
- NET-005: parse `exec-timeout <phút> [<giây>]`; tổng giây = phút*60 + giây. Nếu có nhiều block vty, FAIL nếu **bất kỳ** block nào vi phạm; evidence liệt kê các block vi phạm.
- NET-006: chấp nhận `access-class` kèm tên hoặc số ACL; hướng phải là `in`.
- Rationale/remediation/verification mỗi rule phải cụ thể, ngắn gọn. Ví dụ NET-001 remediation:
  `Restrict VTY lines to SSH: under "line vty 0 4" configure "transport input ssh".`
  verification: `Run "show running-config | section line vty" and confirm transport input contains only ssh.`
- Không kết luận vượt bằng chứng (vd không viết "thiết bị đã bị xâm nhập"; chỉ nói "Telnet is enabled on VTY lines").

---

## 6. Fixtures (`tests/fixtures/configs/`)

Tạo bằng **dữ liệu giả** (tuyệt đối không dùng mật khẩu/community thật):

- `ios_secure.cfg`: cấu hình đạt cả 8 rule (SSHv2, `transport input ssh`, `exec-timeout 5 0`, `access-class 10 in`, `service password-encryption`, `enable secret 9 ...`, `no ip http server`, không có SNMP community).
- `ios_insecure.cfg`: vi phạm cả 8 rule. Dùng các secret giả duy nhất để test rò rỉ: `enable password FAKE-ENABLE-PW`, `username labadmin password 0 FAKE-USER-PW`, `snmp-server community FAKE-COMMUNITY-RW RW`, `transport input telnet ssh`, `exec-timeout 0 0`, `ip http server`, `ip ssh version 1`, vty không có access-class.
- `ios_minimal.cfg`: chỉ có `hostname R1` và vài interface, không có `line vty` (kỳ vọng các rule vty trả UNKNOWN).
- `ios_banner_trap.cfg`: có `banner motd ^C ... transport input telnet ... ^C` nhưng line vty thật chỉ `transport input ssh` (kỳ vọng NET-001 PASS – kiểm chứng parser bỏ qua banner).

---

## 7. Yêu cầu test

Mỗi file test rule phải có tối thiểu: 1 case PASS, 1 case FAIL, 1 case UNKNOWN/edge (nếu rule có UNKNOWN), dùng `pytest.mark.parametrize` và/hoặc fixture file. Test dựng `ParsedConfig` qua `IosConfigParser` từ chuỗi/file.

Test bắt buộc ngoài rule:

1. **Parser**: block + children đúng; bỏ dòng `!`/header IOS; banner nhiều dòng và một dòng; CRLF; đầu vào rỗng.
2. **Redaction**: toàn bộ bảng ở 4.5; idempotent; dòng không có bí mật giữ nguyên.
3. **Không rò rỉ bí mật**: chạy engine trên `ios_insecure.cfg`, `json.dumps` toàn bộ kết quả `to_dict()`, assert không chứa `FAKE-ENABLE-PW`, `FAKE-USER-PW`, `FAKE-COMMUNITY-RW`.
4. **Engine**: rule raise Exception → finding UNKNOWN và các rule khác vẫn chạy; `rule_id` trùng → `ValueError`; kết quả sắp theo `rule_id`; `only_rule_ids`/`skip_rule_ids`; platform không khớp → rule bị bỏ qua; clock giả (fake clock) cho `checked_at` cố định; `device_id` được gắn.
5. **Tính lặp lại**: chạy 2 lần cùng cấu hình + fake clock cho kết quả bằng nhau.
6. **Registry**: 8 rule, `rule_id` duy nhất, mỗi rule có `title`, `severity`, `platforms` không rỗng, `remediation_text` và `verification_text` không rỗng.
7. **Kiến trúc** (`test_architecture_imports.py`): dùng `ast` quét mọi `.py` trong `app/domain` và `app/rules`, assert không import: `fastapi`, `pydantic`, `sqlalchemy`, `netmiko`, `paramiko`, `ollama`, `requests`.
8. Tổng kết kỳ vọng: `ios_secure.cfg` → 8 PASS; `ios_insecure.cfg` → 8 FAIL; `ios_minimal.cfg` → NET-001/005/006 UNKNOWN, các rule còn lại theo đúng bảng mục 5.

---

## 8. Thứ tự thực hiện (dừng và chạy `pytest -q` sau mỗi bước)

1. **Khung dự án**: tạo thư mục, `__init__.py`, `pytest.ini`, `requirements-dev.txt`, cập nhật `.gitignore`.
2. **Domain**: `finding.py`, `parsed_config.py`, `audit_rule.py`, `config_parser.py`. Viết test cho `Finding.to_dict()` và các method của `ParsedConfig`.
3. **Redaction** + `test_redaction.py`.
4. **Parser** + fixtures + `test_ios_config_parser.py`.
5. **BaseRule** + rule NET-001 + test. *(Dừng, tóm tắt cho người dùng xem trước khi làm 7 rule còn lại, để xác nhận phong cách code.)*
6. **Các rule NET-002 → NET-008** + test từng rule.
7. **Engine** + **registry** + `test_engine.py`, test registry, test kiến trúc, test không rò rỉ bí mật.
8. **Script CLI** `scripts/run_rules_on_file.py`, chạy thử trên 4 fixture và dán kết quả vào phần báo cáo.
9. Viết `docs/rules_catalog.md`: bảng 8 rule (ID, mục đích, điều kiện PASS/FAIL/UNKNOWN, ví dụ evidence, remediation).

---

## 9. Tiêu chí hoàn thành (Definition of Done)

- [ ] `cd backend && pytest -q` xanh toàn bộ.
- [ ] 8 rule đăng ký trong `get_default_rules()` với ID NET-001…NET-008.
- [ ] Không file nào trong `app/domain`, `app/rules` import thư viện hạ tầng bị cấm (có test tự động).
- [ ] Không bí mật nào xuất hiện trong output `to_dict()` / JSON / log (có test tự động).
- [ ] Chạy engine không cần thiết bị, không cần mạng.
- [ ] Một rule lỗi không làm hỏng cả lần audit.
- [ ] `scripts/run_rules_on_file.py` chạy được trên cả 4 fixture.
- [ ] Báo cáo cuối: danh sách file đã tạo, kết quả `pytest -q`, và các điểm đặc tả còn mơ hồ cần người dùng quyết định.

---

## 10. Việc để giai đoạn sau (KHÔNG làm ở đây)

- Refactor `ssh_connector.py` thành `CiscoIOSConnector` implement interface `DeviceConnector` (thêm `get_running_config()` bằng `show running-config`).
- `AuditService` (connector → engine → repository), repository SQLite, API route.
- AI explanation (`AIProvider`/Ollama) chỉ nhận finding đã che bí mật.
