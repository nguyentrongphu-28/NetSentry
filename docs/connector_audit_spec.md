# NetSentry – Đặc tả Connector + AuditService cho Antigravity

> Cách dùng: lưu vào `docs/connector_audit_spec.md`, mở Antigravity ở chế độ **Planning**, gửi: *"Đọc @docs/connector_audit_spec.md và thực hiện đúng từng bước ở mục 8. Đưa plan trước, đợi tôi duyệt rồi mới code. Không ghi đè file đã tồn tại mà chưa hỏi."*
> Quy ước ngôn ngữ: giải thích bằng tiếng Việt; tên file/class/hàm, docstring, comment và thông báo lỗi viết bằng tiếng Anh.
> Điều kiện đầu vào: Rule Engine đã xong, `pytest -q` đang xanh (97 test). **Hãy tạo branch mới hoặc commit trước khi bắt đầu.**

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư Python senior. Hãy xây **Device Connector** (kết nối SSH chỉ-đọc tới thiết bị Cisco IOS) và **AuditService** (thiết bị → lấy running-config → Rule Engine → kết quả) cho NetSentry trong `backend/`.

Quy tắc bắt buộc:

1. Làm đúng thứ tự mục 8. Sau mỗi bước chạy `pytest -q` (từ `backend/`) và chỉ đi tiếp khi xanh. **Toàn bộ test hiện có (97) phải tiếp tục xanh.**
2. Không thêm tính năng ngoài phạm vi (mục 1). Nếu đặc tả mơ hồ hoặc mâu thuẫn, **dừng lại và hỏi**.
3. Unit test **không được** mở kết nối mạng thật. Chỉ test `live` (mục 7) mới được, và mặc định bị bỏ qua.
4. Không sửa logic của Rule Engine, parser, rule hiện có. Nếu phát hiện lỗi ở đó, báo cáo chứ không tự sửa.
5. Python 3.11+, type hints đầy đủ, mọi thư mục Python có `__init__.py`.
6. Không bao giờ ghi password/enable secret vào log, exception message, `repr`, kết quả trả về hay file.

---

## 1. Phạm vi

**Làm**

- Domain: lỗi chuẩn (`errors.py`), `DeviceTarget`, `Credentials`, `AuditResult`, interface `DeviceConnector`.
- `CiscoIOSConnector` (Netmiko, chỉ lệnh chỉ-đọc theo allowlist) và `FakeConnector`.
- `ConnectorFactory`.
- `AuditService` (chưa lưu database).
- Script `scripts/audit_device.py` để chạy thử với thiết bị thật.
- Unit test, test kiến trúc cập nhật, một test `live` mặc định bị skip.

**KHÔNG làm**

- Không làm API/FastAPI, repository/SQLite, snapshot/diff, AI, remediation, frontend.
- Không gửi bất kỳ lệnh cấu hình nào lên thiết bị (`configure terminal`, `write`, `reload`, ...).
- `AuditService` không lưu raw config vào `AuditResult` (config có thể chứa bí mật).

---

## 2. Ràng buộc kiến trúc

- `app/domain/` và `app/rules/`: giữ nguyên ràng buộc cũ (chỉ thư viện chuẩn; cấm `fastapi`, `pydantic`, `sqlalchemy`, `netmiko`, `paramiko`, `ollama`, `requests`).
- **Chỉ `app/connectors/`** được import `netmiko` và `paramiko`. Cấm trong `app/services/`, `app/factories/`, `app/domain/`, `app/rules/`.
- `AuditService` chỉ phụ thuộc vào interface (`DeviceConnector`) và `RuleEngine`, nhận chúng qua constructor (Dependency Injection).
- Patterns: **Adapter** (`CiscoIOSConnector` bọc Netmiko), **Factory** (`ConnectorFactory`), **Dependency Injection** (service, session factory, clock).
- Cập nhật `tests/unit/test_architecture_imports.py` để thực thi các ràng buộc trên bằng `ast`.

---

## 3. Cây thư mục (chỉ file thuộc giai đoạn này)

```
backend/
  requirements.txt                  # đảm bảo có netmiko (ghi đúng phiên bản đang cài)
  pytest.ini                        # thêm marker "live" và addopts = -m "not live"
  app/
    domain/
      errors.py
      entities/
        device.py                   # DeviceTarget, Credentials
        audit_result.py             # AuditStatus, AuditResult
      interfaces/
        device_connector.py         # DeviceConnector (ABC)
    connectors/
      __init__.py
      cisco_ios_connector.py        # CiscoIOSConnector
      fake_connector.py             # FakeConnector
    factories/
      __init__.py
      connector_factory.py          # ConnectorFactory, build_default_connector_factory
    services/
      __init__.py
      audit_service.py              # AuditService
  tests/
    unit/
      connectors/
        __init__.py
        test_cisco_ios_connector.py
        test_fake_connector.py
      test_device_entities.py
      test_connector_factory.py
      test_audit_service.py
      test_architecture_imports.py  # cập nhật
    integration/
      __init__.py
      test_cisco_ios_live.py        # marker live
scripts/
  _table.py                         # print_findings_table dùng chung
  run_rules_on_file.py              # chỉ vá nhỏ + dùng _table.py (hành vi không đổi)
  audit_device.py                   # mới
docs/
  connector_audit_flow.md
```

Trước khi tạo file, hãy **tìm file SSH hiện có** (`ssh_connector.py`, hàm `collect_device_info`) và các nơi import nó. **Không xóa và không sửa nó** trong giai đoạn này; chỉ báo cáo vị trí và nơi sử dụng.

---

## 4. Đặc tả từng file

### 4.1 `domain/errors.py`

```python
class NetSentryError(Exception):
    code: str = "NETSENTRY_ERROR"
    def __init__(self, message: str, *, host: str | None = None) -> None: ...

class AuthenticationFailedError(NetSentryError):  code = "AUTH_FAILED"
class ConnectionTimeoutError(NetSentryError):     code = "CONNECT_TIMEOUT"
class ConnectionFailedError(NetSentryError):      code = "CONNECT_FAILED"
class CommandNotAllowedError(NetSentryError):     code = "COMMAND_NOT_ALLOWED"
class ConfigCollectionError(NetSentryError):      code = "COLLECTION_FAILED"
class UnsupportedPlatformError(NetSentryError):   code = "UNSUPPORTED_PLATFORM"
```

Thông báo lỗi do **chính dự án viết** (vd `"SSH authentication failed for 10.0.0.1:22"`), không chép nguyên văn exception của Netmiko/Paramiko. Nguyên nhân gốc giữ qua `raise ... from exc`.

### 4.2 `domain/entities/device.py`

```python
@dataclass(frozen=True, slots=True)
class DeviceTarget:
    device_id: str
    host: str
    platform: str = "cisco_ios"
    port: int = 22

@dataclass(frozen=True, slots=True)
class Credentials:
    username: str
    password: str = field(repr=False)
    enable_secret: str | None = field(default=None, repr=False)
```

- `repr()`/`str()` của `Credentials` **không** chứa password/enable_secret (test).
- Validate trong `__post_init__`: `host`, `device_id`, `username` không rỗng; `1 <= port <= 65535`; ném `ValueError`.

### 4.3 `domain/interfaces/device_connector.py`

```python
class DeviceConnector(ABC):
    platform: str

    @abstractmethod
    def connect(self) -> None: ...
    @abstractmethod
    def close(self) -> None: ...                 # idempotent, không raise
    @abstractmethod
    def get_running_config(self) -> str: ...
    @abstractmethod
    def get_hostname(self) -> str: ...

    def __enter__(self) -> "DeviceConnector":    # gọi connect(), trả về self
    def __exit__(self, *exc) -> None:            # luôn gọi close()
```

### 4.4 `domain/entities/audit_result.py`

```python
class AuditStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass(frozen=True, slots=True)
class AuditResult:
    device_id: str
    platform: str
    status: AuditStatus
    started_at: datetime
    finished_at: datetime
    findings: tuple[Finding, ...] = ()
    hostname: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def pass_count / fail_count / unknown_count -> int
    def to_dict(self) -> dict[str, Any]          # enum → str, datetime → ISO-8601, findings → to_dict()
```

**Không có trường chứa raw config** (test: `not hasattr(result, "config_text")` và không có field nào tên chứa `config`).

### 4.5 `connectors/cisco_ios_connector.py` – `CiscoIOSConnector(DeviceConnector)`

```python
class CiscoIOSConnector(DeviceConnector):
    platform = "cisco_ios"
    ALLOWED_COMMANDS = frozenset({"show running-config", "show version"})

    def __init__(self, target: DeviceTarget, credentials: Credentials, *,
                 timeout: int = 15, command_timeout: int = 60,
                 ssh_config_file: str | None = None,
                 session_factory: Callable[..., Any] | None = None) -> None: ...
```

- `session_factory` mặc định là `netmiko.ConnectHandler`; test truyền session giả vào.
- **Tham số kết nối**: `device_type="cisco_ios"`, `host`, `port`, `username`, `password`, `secret=enable_secret` (nếu có), `conn_timeout/banner_timeout/auth_timeout=timeout`, `use_keys=False`, `allow_agent=False`. **Chỉ** truyền `ssh_config_file` khi tham số khác `None` **và** file tồn tại (không hard-code `/root/.ssh/config`).
- `connect()`:
  - Gọi session factory, lưu session. Gọi lại khi đã kết nối thì không tạo session mới.
  - Nếu prompt kết thúc bằng `>` (chưa vào privileged mode): có `enable_secret` → gọi `enable()`; nếu không có → ném `ConfigCollectionError("Privileged EXEC mode required but no enable secret was provided")` và đóng session.
- **Map lỗi** (kiểm tra tên exception có trong phiên bản Netmiko đang cài, nếu thiếu thì dùng lớp cha `NetmikoBaseException`):
  - `NetmikoAuthenticationException` → `AuthenticationFailedError`
  - `NetmikoTimeoutException` → `ConnectionTimeoutError`
  - `paramiko.SSHException`, `OSError`, `EOFError` → `ConnectionFailedError`
  - Lỗi đọc lệnh quá thời gian (`ReadTimeout` hoặc tương đương) → `ConnectionTimeoutError`
  - Exception khác từ Netmiko khi chạy lệnh → `ConfigCollectionError`
- `get_running_config()` / nội bộ `_run(command)`:
  - **Allowlist**: chuẩn hóa (`strip()`, thu gọn khoảng trắng, lowercase) rồi so khớp **chính xác** với `ALLOWED_COMMANDS`. Từ chối mọi lệnh khác, kể cả lệnh chứa `\n`, `\r`, `;`, `|`, hoặc bắt đầu bằng `conf`/`write`/`reload`/`copy`/`delete`, bằng `CommandNotAllowedError`. Việc kiểm tra xảy ra **trước** khi gọi session.
  - Gửi lệnh bằng `read_timeout=command_timeout`.
  - Output rỗng (sau `strip()`) hoặc bắt đầu bằng/chứa các marker lỗi IOS (`% Invalid input`, `% Authorization failed`, `% Ambiguous command`, `% Incomplete command`) → `ConfigCollectionError`.
  - Chưa `connect()` → `ConnectionFailedError("Not connected")`.
- `get_hostname()`: lấy từ `find_prompt()`, bỏ `#`/`>` cuối và khoảng trắng.
- `close()`: idempotent, bắt mọi exception khi `disconnect()` (chỉ log mức debug, không kèm thông tin nhạy cảm), luôn đặt session về `None`.
- **Logging**: dùng `logging.getLogger(__name__)`. Được log: host, port, device_id, tên lệnh đã chạy, tên lớp exception. **Cấm log**: username, password, enable secret, output lệnh.
- `__repr__` chỉ chứa `device_id`, `host`, `port`.

### 4.6 `connectors/fake_connector.py` – `FakeConnector(DeviceConnector)`

```python
class FakeConnector(DeviceConnector):
    platform = "cisco_ios"
    def __init__(self, config_text: str, hostname: str = "FAKE-R1", *,
                 fail_on: type[NetSentryError] | None = None) -> None: ...
    @classmethod
    def from_file(cls, path: str | Path, **kw) -> "FakeConnector": ...
```

- Trả `config_text` từ `get_running_config()`. Nếu `fail_on` được đặt, `connect()` ném đúng lỗi đó (để test các nhánh lỗi).
- Ghi nhận `connect_calls`, `close_calls` để test kiểm tra connector luôn được đóng.

### 4.7 `factories/connector_factory.py`

```python
ConnectorBuilder = Callable[[DeviceTarget, Credentials], DeviceConnector]

class ConnectorFactory:
    def register(self, platform: str, builder: ConnectorBuilder) -> None: ...   # trùng platform → ValueError
    def create(self, target: DeviceTarget, credentials: Credentials) -> DeviceConnector: ...
    # platform chưa đăng ký → UnsupportedPlatformError

def build_default_connector_factory() -> ConnectorFactory:   # đăng ký "cisco_ios" → CiscoIOSConnector
```

### 4.8 `services/audit_service.py`

```python
class AuditService:
    def __init__(self, connector_factory: ConnectorFactory, engine: RuleEngine,
                 clock: Callable[[], datetime] | None = None) -> None: ...
    def audit_device(self, target: DeviceTarget, credentials: Credentials) -> AuditResult: ...
```

Luồng `audit_device`:

1. `started_at = clock()`.
2. `connector = factory.create(target, credentials)`; `with connector:` → lấy `hostname` và `config_text`.
3. `findings = engine.run(config_text, platform=target.platform, device_id=target.device_id)`.
4. Trả `AuditResult(status=COMPLETED, findings=tuple(findings), hostname=..., finished_at=clock())`. **Không** giữ `config_text` sau khi xong.
5. Bắt `NetSentryError` → `AuditResult(status=FAILED, error_code=exc.code, error_message=str(exc), findings=())`.
6. Bắt `Exception` khác → `logger.exception(...)` (không kèm cấu hình/credential) và trả `FAILED` với `error_code="INTERNAL_ERROR"`, `error_message="Unexpected error during audit"`. Không lộ chi tiết exception trong kết quả.
7. Connector **luôn** được đóng (kể cả khi lỗi), nhờ `with`.
8. `audit_device` không raise ra ngoài trong mọi trường hợp (trừ `KeyboardInterrupt`/`SystemExit`).

### 4.9 `scripts/_table.py` và vá `scripts/run_rules_on_file.py`

- Chuyển hàm in bảng (`print_table`) sang `scripts/_table.py` thành `print_findings_table(findings, device_id, title)`, in đúng định dạng hiện tại (rule_id | status | severity | title, kèm dòng Evidence, và dòng Summary).
- Sửa `run_rules_on_file.py` để dùng hàm chung và vá 3 điểm nhỏ:
  - `args.config_path.is_file()` thay cho `exists()`;
  - `read_text(encoding="utf-8", errors="replace")`;
  - bỏ biến `status_color` gây hiểu nhầm.
- Hành vi và output của script phải **giữ nguyên**. Chạy lại trên 4 fixture để xác nhận.

### 4.10 `scripts/audit_device.py`

```
python scripts/audit_device.py --host 10.0.0.1 [--port 22] [--device-id R1]
       [--platform cisco_ios] [--json] [--dump-config data/raw_configs/R1.cfg]
```

- Credentials lấy từ biến môi trường: `NETSENTRY_SSH_USERNAME`, `NETSENTRY_SSH_PASSWORD`, `NETSENTRY_ENABLE_SECRET` (tuỳ chọn). Nếu thiếu username/password và đang chạy trong terminal tương tác thì hỏi bằng `input()` / `getpass.getpass()`. **Không** có tham số dòng lệnh nhận password.
- `--device-id` mặc định là `--host`.
- Dựng engine bằng `build_default_engine()`, factory bằng `build_default_connector_factory()`, chạy `AuditService.audit_device`.
- Hiển thị: bảng text (dùng `print_findings_table`) hoặc JSON (`AuditResult.to_dict()`).
- Nếu `AuditResult.status == FAILED`: in `error_code` + `error_message` ra stderr, thoát mã **2**. Lỗi tham số/credential thiếu: mã **1**. Thành công: mã **0**.
- `--dump-config PATH` (tuỳ chọn, mặc định tắt): lưu running-config thô để người dùng debug rule trên thiết bị thật. In cảnh báo: *"Raw config may contain secrets. Keep it out of Git."* Chỉ cho ghi vào thư mục `data/raw_configs/` (từ chối đường dẫn khác), tạo thư mục nếu cần, đặt quyền file `0o600` nếu hệ điều hành hỗ trợ. Vì `AuditResult` không chứa config, phần này lấy config bằng cách gọi connector riêng, hoặc service cung cấp hook tuỳ chọn; chọn cách đơn giản nhất mà **không** làm `AuditResult` chứa config, và nêu lựa chọn trong plan để người dùng duyệt.
- Chạy từ bất kỳ thư mục làm việc nào (thêm `backend/` vào `sys.path` như `run_rules_on_file.py`).

---

## 5. Hành vi lỗi cần thống nhất

| Tình huống | Exception từ connector | `AuditResult.error_code` |
|---|---|---|
| Sai username/password | `AuthenticationFailedError` | `AUTH_FAILED` |
| Host không phản hồi / timeout kết nối | `ConnectionTimeoutError` | `CONNECT_TIMEOUT` |
| Từ chối kết nối, SSH lỗi, rớt kết nối | `ConnectionFailedError` | `CONNECT_FAILED` |
| Chưa vào privileged mode, không có enable secret | `ConfigCollectionError` | `COLLECTION_FAILED` |
| Lệnh bị IOS từ chối (`% Invalid input`...) | `ConfigCollectionError` | `COLLECTION_FAILED` |
| Gọi lệnh ngoài allowlist | `CommandNotAllowedError` | `COMMAND_NOT_ALLOWED` |
| Platform chưa đăng ký | `UnsupportedPlatformError` | `UNSUPPORTED_PLATFORM` |
| Lỗi không lường trước | (bất kỳ) | `INTERNAL_ERROR` |

---

## 6. Yêu cầu test (unit)

`FakeSession` trong test mô phỏng đối tượng Netmiko: `find_prompt()`, `send_command(cmd, read_timeout=...)`, `enable()`, `check_enable_mode()`, `disconnect()`, ghi lại các lệnh đã nhận.

1. **CiscoIOSConnector** (`test_cisco_ios_connector.py`, dùng `session_factory` giả):
   - Thành công: `get_running_config()` trả đúng output, `get_hostname()` bỏ `#`.
   - Tham số truyền vào session factory: `device_type="cisco_ios"`, `use_keys=False`, `allow_agent=False`; **không có** khóa `ssh_config_file` khi tham số là `None` hoặc file không tồn tại; có khi file tồn tại.
   - Allowlist: parametrize các lệnh bị từ chối (`configure terminal`, `show running-config; reload`, `show run`, `show running-config | include password`, `write memory`, `reload`, lệnh có `\n`) → `CommandNotAllowedError`, và **session không nhận lệnh nào**.
   - Map lỗi: factory raise `NetmikoAuthenticationException` → `AuthenticationFailedError`; `NetmikoTimeoutException` → `ConnectionTimeoutError`; `OSError`/`paramiko.SSHException` → `ConnectionFailedError`; lỗi đọc lệnh quá hạn → `ConnectionTimeoutError`.
   - Privileged mode: prompt `R1>` + có enable secret → `enable()` được gọi; prompt `R1>` + không có secret → `ConfigCollectionError` và session được đóng.
   - Output lỗi (`% Invalid input detected`) và output rỗng → `ConfigCollectionError`.
   - `close()` idempotent; `with` luôn đóng session kể cả khi bên trong ném lỗi; `disconnect()` ném lỗi cũng không làm `close()` raise.
   - **Không rò rỉ**: dùng `caplog` ở mức DEBUG, chạy các luồng thành công và lỗi; assert password/enable secret/username giả (`FAKE-SSH-PW`, `FAKE-ENABLE-PW`, `fake-user`) không xuất hiện trong log, `repr(connector)`, `str(exception)`.
2. **Entities** (`test_device_entities.py`): `Credentials` repr/str không chứa password; validate `DeviceTarget`/`Credentials` (rỗng, port ngoài khoảng); `AuditResult.to_dict()` (enum → str, ISO-8601, đếm PASS/FAIL/UNKNOWN); không có trường nào chứa raw config.
3. **FakeConnector**: trả đúng config, `from_file`, `fail_on` ném đúng lỗi, `close_calls` tăng.
4. **ConnectorFactory**: tạo đúng connector; platform lạ → `UnsupportedPlatformError`; đăng ký trùng → `ValueError`; `build_default_connector_factory()` tạo được `CiscoIOSConnector` cho `cisco_ios` (không kết nối thật).
5. **AuditService** (dùng `FakeConnector` + `build_default_engine()` + fake clock):
   - `ios_insecure.cfg` → `COMPLETED`, 8 finding FAIL; `ios_secure.cfg` → 8 PASS; `hostname`, `device_id`, `platform`, `started_at/finished_at` đúng.
   - Parametrize `fail_on` cho từng lỗi trong mục 5 → `FAILED`, `error_code` đúng, `findings == ()`, không raise.
   - Connector ném `RuntimeError("secret-stuff")` → `INTERNAL_ERROR`, `error_message` chung chung và **không** chứa `secret-stuff`.
   - `close_calls == 1` trong mọi trường hợp (thành công và lỗi).
   - Platform lạ → `UNSUPPORTED_PLATFORM`.
   - Không rò rỉ: `json.dumps(result.to_dict())` không chứa chuỗi bí mật giả có trong fixture.
6. **Kiến trúc** (`test_architecture_imports.py`, cập nhật): quét `ast` — `netmiko`/`paramiko` chỉ được import trong `app/connectors/`; `app/domain`, `app/rules`, `app/services`, `app/factories` không import `fastapi`, `pydantic`, `sqlalchemy`, `netmiko`, `paramiko`, `ollama`, `requests`.

---

## 7. Test live (tuỳ chọn, mặc định bị bỏ qua)

- Thêm vào `pytest.ini`:
  ```ini
  markers =
      live: tests that connect to a real device (deselected by default)
  addopts = -m "not live"
  ```
- `tests/integration/test_cisco_ios_live.py` (`@pytest.mark.live`): đọc `NETSENTRY_LIVE_HOST`, `NETSENTRY_SSH_USERNAME`, `NETSENTRY_SSH_PASSWORD`, (tuỳ chọn) `NETSENTRY_ENABLE_SECRET`; nếu thiếu biến thì `pytest.skip`. Kiểm tra `AuditService.audit_device` trả `COMPLETED` và đủ 8 finding. Chỉ chạy khi người dùng gọi `pytest -m live`.

---

## 8. Thứ tự thực hiện (dừng và chạy `pytest -q` sau mỗi bước)

1. **Chuẩn bị**: tìm và báo cáo file SSH cũ cùng nơi sử dụng (không sửa); đảm bảo `netmiko` có trong `requirements.txt`; cập nhật `pytest.ini` (marker `live`, `addopts`). Chạy `pytest -q` để xác nhận 97 test vẫn xanh.
2. **Domain**: `errors.py`, `device.py`, `audit_result.py`, `device_connector.py` + `test_device_entities.py`.
3. **FakeConnector + ConnectorFactory** + test của chúng.
4. **CiscoIOSConnector** + `test_cisco_ios_connector.py` (đầy đủ allowlist, map lỗi, không rò rỉ). **DỪNG LẠI**: tóm tắt thiết kế connector (tham số kết nối, allowlist, map lỗi) và danh sách test, chờ người dùng duyệt trước khi làm tiếp.
5. **AuditService** + `test_audit_service.py`.
6. **Cập nhật test kiến trúc** (`test_architecture_imports.py`).
7. **Scripts**: `_table.py`, vá `run_rules_on_file.py` (chạy lại 4 fixture để chứng minh output không đổi), `audit_device.py` (chạy thử với `--help`, và thử với host không tồn tại để kiểm tra mã thoát 2 và thông báo lỗi không lộ bí mật).
8. **Test live** (`test_cisco_ios_live.py`, mặc định skip) và `docs/connector_audit_flow.md` (sơ đồ luồng, bảng lỗi mục 5, hướng dẫn chạy `audit_device.py`, cảnh báo về `--dump-config`).
9. **Báo cáo cuối**: danh sách file tạo/sửa, kết quả `pytest -q` (số test, kèm 97 cũ), kết quả thử script, các điểm mơ hồ còn lại.

---

## 9. Tiêu chí hoàn thành

- [ ] `cd backend && pytest -q` xanh, bao gồm 97 test cũ; `pytest -m live` không bị lỗi cấu hình marker.
- [ ] Không có kết nối mạng thật trong unit test.
- [ ] Connector chỉ chạy được `show running-config` và `show version`; mọi lệnh khác bị từ chối trước khi chạm vào session.
- [ ] Không có password, enable secret hay username nào trong log, `repr`, exception message, `AuditResult` hay JSON đầu ra (có test).
- [ ] `AuditResult` không chứa raw config.
- [ ] `AuditService.audit_device` không raise trong mọi tình huống lỗi; connector luôn được đóng.
- [ ] `netmiko`/`paramiko` chỉ xuất hiện trong `app/connectors/` (có test).
- [ ] `scripts/audit_device.py` chạy được; mã thoát đúng (0/1/2); không nhận password qua tham số dòng lệnh.
- [ ] `run_rules_on_file.py` vẫn cho cùng output trên 4 fixture.
- [ ] File SSH cũ **chưa bị xóa** (chờ người dùng quyết định).

---

## 10. Để giai đoạn sau (KHÔNG làm ở đây)

- Repository + SQLite: lưu `Device`, `AuditRun`, `Finding`.
- API FastAPI (`POST /devices/{id}/audit`, `GET /audits/{id}/findings`), schema Pydantic.
- Snapshot + diff cấu hình (khi đó mới lưu config, đã che bí mật).
- Xóa/chuyển file SSH cũ sau khi `CiscoIOSConnector` đã kiểm chứng trên thiết bị thật.
- Remediation có phê duyệt (khi đó mới mở rộng allowlist theo từng lệnh cụ thể).
