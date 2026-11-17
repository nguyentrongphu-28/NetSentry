# NetSentry – Đặc tả Repository (SQLite) + REST API (FastAPI) cho Antigravity

> Cách dùng: lưu vào `docs/persistence_api_spec.md`, mở Antigravity ở chế độ **Planning**, gửi: *"Đọc @docs/persistence_api_spec.md và thực hiện đúng từng bước ở mục 9. Đưa plan trước, đợi tôi duyệt rồi mới code. Không ghi đè file không rỗng mà chưa hỏi."*
> Quy ước ngôn ngữ: giải thích bằng tiếng Việt; tên file/class/hàm, docstring, comment, thông báo lỗi và mô tả API viết bằng tiếng Anh.
> Điều kiện đầu vào: Rule Engine + Connector + AuditService đã xong, `pytest -q` đang xanh (178 test), audit thật trên router đã chạy được. **Hãy tạo branch mới hoặc commit trước khi bắt đầu.**

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư Python backend senior. Hãy xây **lớp lưu trữ SQLite** (Device, AuditRun, Finding) và **REST API FastAPI** để điều khiển `AuditService` hiện có, trong `backend/`.

Quy tắc bắt buộc:

1. Làm đúng thứ tự mục 9. Sau mỗi bước chạy `pytest -q` (từ `backend/`), chỉ đi tiếp khi xanh. **178 test hiện có phải tiếp tục xanh.**
2. Không thêm tính năng ngoài phạm vi (mục 1). Đặc tả mơ hồ hoặc mâu thuẫn → **dừng lại và hỏi**.
3. Unit/API test **không** mở kết nối mạng thật; dùng `FakeConnector`. Không đổi test `live`.
4. Không sửa logic Rule Engine, parser, rule, `CiscoIOSConnector`, `AuditService` hiện có. Chỉ được **thêm** (ví dụ thêm lớp lỗi vào `domain/errors.py`, thêm entity vào `domain/entities/`). Nếu cần sửa file hiện có ngoài việc thêm, hãy hỏi.
5. **Không đụng vào phiên bản `netmiko` và `paramiko`** trong `requirements`. Server chạy bằng venv đặc biệt (paramiko đời cũ cho router lab); thư viện mới thêm vào không được kéo nâng/hạ hai gói này.
6. Python 3.11+, type hints đầy đủ, mọi thư mục Python có `__init__.py`.
7. Không bao giờ lưu, log, trả về hay đưa vào lỗi: password, enable secret, API key, raw running-config.
8. Trước khi tạo file, liệt kê các file đã tồn tại trong cây thư mục mục 3 kèm `wc -c`. File **0 byte** được phép ghi đè; file **không rỗng** thì hỏi trước.

---

## 1. Phạm vi

**Làm**

- Domain: `Device`, `AuditRunSummary`, `AuditRunDetail`, interface `DeviceRepository`, `AuditRepository`, các lỗi mới.
- SQLite (thư viện chuẩn `sqlite3`, truy vấn tham số hóa): `database.py`, schema, `SqliteDeviceRepository`, `SqliteAuditRepository`.
- Services: `DeviceService`, `AuditRunService` (khóa chống chạy audit trùng cho cùng một thiết bị).
- FastAPI: `create_app`, auth bằng API key, các route mục 6, schema Pydantic, xử lý lỗi thống nhất.
- Cấu hình qua biến môi trường (`core/config.py`).
- Test đầy đủ, cập nhật test kiến trúc, tài liệu `docs/api_and_persistence.md`.

**KHÔNG làm**

- Không frontend, AI/Ollama, snapshot/diff, remediation, tài khoản người dùng/phân quyền, background job/hàng đợi, WebSocket, migration framework (Alembic).
- **Không lưu credential thiết bị vào database** (dưới mọi hình thức, kể cả mã hóa).
- Không route liệt kê finding xuyên nhiều thiết bị (để giai đoạn sau).
- Không sửa/xóa file SSH cũ (`ssh_connector.py`, `scripts/test_cisco_connection.py`), `finding_repository.py`, `ai_explainer.py`, `ollama_client.py` (giữ nguyên placeholder).

---

## 2. Ràng buộc kiến trúc

- `app/domain/`, `app/rules/`: giữ ràng buộc cũ (chỉ thư viện chuẩn).
- `sqlite3` chỉ được import trong `app/repositories/`.
- `fastapi`, `pydantic`, `starlette`, `uvicorn` chỉ được import trong `app/api/` và `app/main.py`. **Cấm** trong `domain`, `rules`, `services`, `factories`, `connectors`, `repositories`, `core`.
- `netmiko`/`paramiko` chỉ trong `app/connectors/` (giữ nguyên).
- `services` phụ thuộc interface (repository, `AuditService`), nhận qua constructor (DI). `api` chỉ gọi `services`, không gọi repository trực tiếp.
- Cập nhật `tests/unit/test_architecture_imports.py` bằng `ast` để thực thi toàn bộ ràng buộc trên.
- Endpoint viết bằng `def` (đồng bộ) vì connector SSH là blocking; FastAPI sẽ chạy chúng trong threadpool.

---

## 3. Cây thư mục (chỉ file thuộc giai đoạn này)

```
backend/
  requirements.txt                 # thêm fastapi, uvicorn[standard], httpx (cho TestClient); ghim phiên bản
  app/
    main.py                        # create_app(...) factory; KHÔNG tạo app ở mức module
    core/
      config.py                    # Settings, ConfigError
      dependencies.py              # providers + xác thực API key
    domain/
      errors.py                    # THÊM lỗi mới (không sửa lỗi cũ)
      entities/
        device.py                  # THÊM class Device (giữ nguyên DeviceTarget, Credentials)
        audit_run.py               # AuditRunSummary, AuditRunDetail
      interfaces/
        device_repository.py       # DeviceRepository (ABC)
        audit_repository.py        # AuditRepository (ABC)
    repositories/
      __init__.py
      database.py                  # connect(), init_db(), SCHEMA_SQL
      device_repository.py         # SqliteDeviceRepository
      audit_repository.py          # SqliteAuditRepository
    services/
      device_service.py            # DeviceService
      audit_run_service.py         # AuditRunService
    api/
      __init__.py
      errors.py                    # exception handlers
      schemas/
        __init__.py
        device.py
        audit.py
        common.py
      routes/
        __init__.py
        health.py
        devices.py
        audits.py
  tests/
    unit/
      test_config.py
      repositories/
        __init__.py
        test_database.py
        test_device_repository.py
        test_audit_repository.py
      services/
        __init__.py
        test_device_service.py
        test_audit_run_service.py
      test_architecture_imports.py # cập nhật
    api/
      __init__.py
      conftest.py                  # fixture app + TestClient + FakeConnector
      test_auth.py
      test_devices_api.py
      test_audits_api.py
      test_security_api.py
docs/
  api_and_persistence.md
```

`.gitignore`: thêm `data/*.db`, `data/*.db-wal`, `data/*.db-shm` (nếu chưa có).

---

## 4. Đặc tả domain

### 4.1 Lỗi mới (`domain/errors.py`, chỉ thêm)

```python
class DeviceNotFoundError(NetSentryError):       code = "DEVICE_NOT_FOUND"
class DuplicateDeviceError(NetSentryError):      code = "DEVICE_EXISTS"
class InvalidDeviceError(NetSentryError):        code = "INVALID_DEVICE"
class AuditNotFoundError(NetSentryError):        code = "AUDIT_NOT_FOUND"
class AuditAlreadyRunningError(NetSentryError):  code = "AUDIT_ALREADY_RUNNING"
class CredentialsRequiredError(NetSentryError):  code = "CREDENTIALS_REQUIRED"
```

### 4.2 Entity

```python
# device.py (thêm)
@dataclass(frozen=True, slots=True)
class Device:
    device_id: str
    name: str
    host: str
    port: int
    platform: str
    created_at: datetime
    updated_at: datetime
    def to_target(self) -> DeviceTarget: ...

# audit_run.py
@dataclass(frozen=True, slots=True)
class AuditRunSummary:
    id: int
    device_id: str
    platform: str
    status: AuditStatus
    started_at: datetime
    finished_at: datetime
    hostname: str | None
    error_code: str | None
    error_message: str | None
    pass_count: int
    fail_count: int
    unknown_count: int

@dataclass(frozen=True, slots=True)
class AuditRunDetail:
    summary: AuditRunSummary
    findings: tuple[Finding, ...]
```

Không entity nào có trường chứa credential hoặc raw config.

### 4.3 Interface repository

```python
class DeviceRepository(ABC):
    def add(self, device: Device) -> None: ...                 # trùng device_id hoặc (host, port) → DuplicateDeviceError
    def get(self, device_id: str) -> Device | None: ...
    def list(self) -> list[Device]: ...                        # sắp theo device_id
    def delete(self, device_id: str) -> bool: ...              # True nếu có xóa; cascade audit_runs + findings

class AuditRepository(ABC):
    def save_run(self, result: AuditResult) -> int: ...        # 1 transaction; device không tồn tại → DeviceNotFoundError
    def get_run(self, run_id: int) -> AuditRunDetail | None: ...
    def list_runs(self, device_id: str, *, limit: int = 20, offset: int = 0) -> tuple[list[AuditRunSummary], int]: ...  # (items, total), mới nhất trước
    def latest_run(self, device_id: str) -> AuditRunSummary | None: ...
```

---

## 5. Đặc tả lưu trữ SQLite

### 5.1 `repositories/database.py`

- `connect(db_path: str | Path) -> sqlite3.Connection`: mở **một kết nối mới cho mỗi lần gọi** (an toàn đa luồng), `row_factory = sqlite3.Row`, đặt `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = 5000`, `PRAGMA journal_mode = WAL` (bỏ qua nếu là file tạm không hỗ trợ). Tạo thư mục cha nếu chưa có.
- `init_db(db_path)`: idempotent; chạy `SCHEMA_SQL`, đặt `PRAGMA user_version = 1`. Nếu `user_version` lớn hơn phiên bản code biết → `RuntimeError` rõ ràng.
- **Mọi truy vấn dùng tham số `?`**, tuyệt đối không nối chuỗi từ dữ liệu người dùng.
- Mỗi thao tác ghi dùng `with conn:` (commit/rollback) và đóng kết nối trong `finally`.

### 5.2 Schema

```sql
CREATE TABLE IF NOT EXISTS devices (
  device_id  TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  host       TEXT NOT NULL,
  port       INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
  platform   TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (host, port)
);

CREATE TABLE IF NOT EXISTS audit_runs (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id      TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  platform       TEXT NOT NULL,
  status         TEXT NOT NULL CHECK (status IN ('COMPLETED','FAILED')),
  started_at     TEXT NOT NULL,
  finished_at    TEXT NOT NULL,
  hostname       TEXT,
  error_code     TEXT,
  error_message  TEXT,
  pass_count     INTEGER NOT NULL DEFAULT 0,
  fail_count     INTEGER NOT NULL DEFAULT 0,
  unknown_count  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_audit_runs_device_started ON audit_runs(device_id, started_at DESC);

CREATE TABLE IF NOT EXISTS findings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  audit_run_id  INTEGER NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
  rule_id       TEXT NOT NULL,
  title         TEXT NOT NULL,
  severity      TEXT NOT NULL CHECK (severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
  status        TEXT NOT NULL CHECK (status IN ('PASS','FAIL','UNKNOWN')),
  evidence_json TEXT NOT NULL,
  rationale     TEXT NOT NULL,
  remediation   TEXT NOT NULL,
  verification  TEXT NOT NULL,
  checked_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(audit_run_id);
```

- Thời gian lưu dạng ISO-8601 UTC (`datetime.isoformat()`), đọc lại thành `datetime` có timezone.
- `evidence_json` là JSON list các chuỗi (đã che bí mật từ trước); đọc lại thành `tuple[str, ...]`.
- Bảng **không có cột** nào cho password/secret/config.

### 5.3 Repository

- `SqliteDeviceRepository(db_path)` và `SqliteAuditRepository(db_path)` nhận đường dẫn, mỗi phương thức mở/đóng kết nối riêng.
- `save_run`: chèn `audit_runs` + toàn bộ `findings` trong **một transaction**; lưu `pass/fail/unknown_count` từ `AuditResult`. Vi phạm khóa ngoại → `DeviceNotFoundError`.
- `get_run`: trả `AuditRunDetail`, findings sắp theo `rule_id`.
- `list_runs`: sắp `started_at DESC, id DESC`; `limit` tối đa 200 (giá trị lớn hơn bị kẹp xuống 200), `offset >= 0`.

---

## 6. Đặc tả services

### 6.1 `services/device_service.py` – `DeviceService`

```python
class DeviceService:
    def __init__(self, repository: DeviceRepository, *, allowed_networks: Sequence[IPv4Network | IPv6Network] = (),
                 clock: Callable[[], datetime] | None = None) -> None: ...
    def create(self, device_id: str, host: str, *, name: str | None = None, port: int = 22,
               platform: str = "cisco_ios") -> Device: ...
    def get(self, device_id: str) -> Device                    # thiếu → DeviceNotFoundError
    def list(self) -> list[Device]
    def delete(self, device_id: str) -> None                   # thiếu → DeviceNotFoundError
```

- `name` mặc định bằng `device_id`.
- Validate (ném `InvalidDeviceError`): `device_id` khớp `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`; `host` là IPv4/IPv6 hợp lệ **hoặc** hostname hợp lệ (nhãn chữ-số-gạch ngang, tổng ≤ 253 ký tự, không khoảng trắng, không `/`, `:` (trừ IPv6), `@`, `?`, `#`); `port` 1–65535; `platform` hiện chỉ chấp nhận `cisco_ios`.
- **Allowlist mạng** (SSRF hygiene): nếu `allowed_networks` không rỗng thì `host` **phải là địa chỉ IP** nằm trong ít nhất một mạng cho phép; hostname bị từ chối (không phân giải DNS).

### 6.2 `services/audit_run_service.py` – `AuditRunService`

```python
class AuditRunService:
    def __init__(self, device_repository: DeviceRepository, audit_repository: AuditRepository,
                 audit_service: AuditService, *, default_credentials: Callable[[], Credentials | None] | None = None) -> None: ...
    def run_audit(self, device_id: str, credentials: Credentials | None = None) -> AuditRunDetail: ...
    def get_run(self, run_id: int) -> AuditRunDetail            # thiếu → AuditNotFoundError
    def list_runs(self, device_id: str, *, limit: int = 20, offset: int = 0) -> tuple[list[AuditRunSummary], int]
    def latest_run(self, device_id: str) -> AuditRunSummary | None
```

`run_audit`:

1. Lấy device (thiếu → `DeviceNotFoundError`).
2. Chọn credentials: tham số truyền vào, nếu không có thì `default_credentials()` (đọc từ biến môi trường), nếu vẫn không có → `CredentialsRequiredError`.
3. **Khóa theo thiết bị**: giữ `dict[str, threading.Lock]` (bảo vệ bằng một lock chung). Nếu khóa của thiết bị đang bị giữ → `AuditAlreadyRunningError` ngay (không chờ, `acquire(blocking=False)`). Luôn nhả khóa trong `finally`, kể cả khi lỗi.
4. Gọi `audit_service.audit_device(device.to_target(), credentials)` (không raise; trả `AuditResult` COMPLETED hoặc FAILED).
5. `save_run(result)` rồi `get_run(id)` và trả về `AuditRunDetail`. Audit **FAILED** (lỗi kết nối) vẫn được lưu như một run.
6. Không giữ, không ghi credential ở bất cứ đâu sau khi xong.

---

## 7. Đặc tả cấu hình và API

### 7.1 `core/config.py`

```python
@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    api_key: str | None = field(repr=False)
    auth_disabled: bool
    cors_origins: tuple[str, ...]
    allowed_networks: tuple[IPv4Network | IPv6Network, ...]
    enable_docs: bool
    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings": ...

class ConfigError(Exception): ...
```

Biến môi trường:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `NETSENTRY_DB_PATH` | `<repo>/data/netsentry.db` | File SQLite |
| `NETSENTRY_API_KEY` | – | **Bắt buộc**, tối thiểu 16 ký tự, trừ khi `NETSENTRY_AUTH_DISABLED=1` |
| `NETSENTRY_AUTH_DISABLED` | `0` | Chỉ để dev; khi bật phải `logger.warning` lúc khởi động |
| `NETSENTRY_CORS_ORIGINS` | rỗng | Danh sách origin cách nhau bằng dấu phẩy |
| `NETSENTRY_ALLOWED_NETWORKS` | rỗng | Danh sách CIDR cách nhau bằng dấu phẩy |
| `NETSENTRY_ENABLE_DOCS` | `1` | Bật/tắt `/docs`, `/redoc`, `/openapi.json` |
| `NETSENTRY_SSH_USERNAME`, `NETSENTRY_SSH_PASSWORD`, `NETSENTRY_SSH_ENABLE_SECRET`... | – | Credentials dự phòng khi request không gửi credentials (tên biến enable secret **giữ đúng** tên mà `audit_device.py` đang dùng) |

`from_env` thiếu/không hợp lệ → `ConfigError` với thông báo rõ ràng, **không** in giá trị bí mật. `repr(Settings)` không chứa API key.

### 7.2 `main.py`

```python
def create_app(settings: Settings | None = None, *, connector_factory: ConnectorFactory | None = None) -> FastAPI: ...
```

- Không có `app = ...` ở mức module. Chạy bằng: `uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000` (từ `backend/`).
- Khi khởi tạo: `Settings.from_env()` nếu không truyền; `init_db`; dựng repository, `build_default_engine()`, `connector_factory or build_default_connector_factory()`, `AuditService`, `DeviceService`, `AuditRunService`; lưu vào `app.state` (hoặc dependency) để route lấy qua `Depends`.
- CORS: chỉ bật khi `cors_origins` không rỗng; `allow_methods=["GET","POST","DELETE"]`, `allow_headers=["X-API-Key","Content-Type"]`, `allow_credentials=False`.
- Tất cả route dưới prefix `/api/v1` (trừ `/health`); `enable_docs=False` thì tắt docs.

### 7.3 Xác thực

- Header `X-API-Key`, khai báo bằng `fastapi.security.APIKeyHeader(auto_error=False)` (để Swagger có nút Authorize).
- So sánh bằng `secrets.compare_digest`. Thiếu/sai → **401** `{"error": {"code": "UNAUTHORIZED", "message": "Invalid or missing API key"}}`.
- Áp dụng cho mọi route **trừ** `GET /health`. Khi `auth_disabled=True` thì bỏ qua kiểm tra.
- Không bao giờ log giá trị API key hay header.

### 7.4 Danh sách endpoint (`/api/v1`)

| Method | Path | Mô tả | Mã thành công | Lỗi |
|---|---|---|---|---|
| GET | `/health` (ngoài prefix, không cần key) | `{"status":"ok","version":"<str>"}` | 200 | – |
| POST | `/devices` | Tạo thiết bị | 201 `DeviceOut` | 409 `DEVICE_EXISTS`, 422 `INVALID_DEVICE`/validation |
| GET | `/devices` | `{"items":[DeviceOut + latest_audit]}` | 200 | – |
| GET | `/devices/{device_id}` | Một thiết bị + `latest_audit` | 200 | 404 `DEVICE_NOT_FOUND` |
| DELETE | `/devices/{device_id}` | Xóa thiết bị và lịch sử audit | 204 | 404 |
| POST | `/devices/{device_id}/audit` | Chạy audit (đồng bộ) | 201 `AuditRunDetailOut` | 404, 409 `AUDIT_ALREADY_RUNNING`, 422 `CREDENTIALS_REQUIRED` |
| GET | `/devices/{device_id}/audits?limit=&offset=` | `{"items":[AuditRunSummaryOut],"total","limit","offset"}` | 200 | 404 |
| GET | `/audits/{run_id}` | Chi tiết run + findings | 200 | 404 `AUDIT_NOT_FOUND` |
| GET | `/audits/{run_id}/findings?status=&severity=` | Lọc findings (giá trị lọc không hợp lệ → 422) | 200 | 404 |

Quy ước:

- `POST /devices/{id}/audit`: body **tùy chọn** `{"credentials": {"username": "...", "password": "...", "enable_secret": null}}`. Bỏ trống body thì dùng credentials dự phòng từ biến môi trường. Audit mà kết nối thiết bị lỗi vẫn trả **201** với `status="FAILED"`, `error_code`, `error_message` (vì run đã được ghi nhận); client phân biệt bằng trường `status`.
- `latest_audit` là `AuditRunSummaryOut | null`.
- Thời gian trả về dạng ISO-8601.
- Mọi lỗi có dạng `{"error": {"code": "...", "message": "..."}}`. Ánh xạ: `DeviceNotFoundError`/`AuditNotFoundError` → 404; `DuplicateDeviceError`/`AuditAlreadyRunningError` → 409; `InvalidDeviceError`/`CredentialsRequiredError` → 422; `UNAUTHORIZED` → 401; lỗi không lường trước → 500 `INTERNAL_ERROR` với thông báo chung, `logger.exception` **không** kèm body request.
- **Lỗi validation 422 của FastAPI phải được ghi đè** (`RequestValidationError` handler): trả `{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": [{"field": "...", "message": "..."}]}}` và **tuyệt đối không** chứa trường `input` hay giá trị client gửi (mặc định FastAPI trả lại giá trị đã gửi, sẽ làm lộ password).

### 7.5 Schema Pydantic (`api/schemas/`)

- `DeviceCreate`: `device_id` (regex trên), `host` (str, 1–253), `name` (tuỳ chọn, ≤ 100), `port` (1–65535, mặc định 22), `platform` (`Literal["cisco_ios"]`, mặc định `cisco_ios`). `model_config = ConfigDict(extra="forbid")`.
- `CredentialsIn`: `username` (str, 1–64), `password` (`SecretStr`), `enable_secret` (`SecretStr | None`), `extra="forbid"`. `repr` không lộ bí mật.
- `AuditRequest`: `credentials: CredentialsIn | None = None`, `extra="forbid"`.
- `DeviceOut`, `LatestAuditOut`/`AuditRunSummaryOut`, `FindingOut`, `AuditRunDetailOut`, `ErrorResponse`.
- Chuyển đổi domain → schema ở lớp API (hàm/`classmethod` trong `schemas`), không để domain biết Pydantic.
- Route khai báo `responses=` cho các mã lỗi để OpenAPI mô tả đủ.

---

## 8. Yêu cầu test

Dùng file SQLite trong `tmp_path` (không dùng `:memory:` vì mỗi kết nối có DB riêng). API test dùng `TestClient`, `create_app(Settings(...), connector_factory=<factory đăng ký FakeConnector>)`; `FakeConnector` nạp `ios_insecure.cfg`/`ios_secure.cfg`.

1. **Database**: `init_db` idempotent; `user_version = 1`; `foreign_keys` bật; từ chối `user_version` lớn hơn.
2. **DeviceRepository**: add/get/list/delete; trùng `device_id` và trùng `(host, port)` → `DuplicateDeviceError`; xóa cascade `audit_runs` và `findings` (đếm bảng sau khi xóa); `device_id` chứa ký tự nguy hiểm (`x'; DROP TABLE devices;--`) được lưu như chuỗi thường, bảng vẫn nguyên vẹn.
3. **AuditRepository**: round-trip run 8 finding (`Finding` đọc lại bằng nhau: evidence là tuple, enum, `checked_at`); lưu run FAILED với 0 finding; thứ tự `list_runs` mới nhất trước; phân trang + `total`; `limit` bị kẹp 200; `latest_run`; `get_run` không tồn tại → `None`; `save_run` cho device không tồn tại → `DeviceNotFoundError` và không để lại bản ghi dở (transaction).
4. **DeviceService**: validate (`device_id`, `host`, `port`, `platform`); allowlist (IP trong/ngoài CIDR, hostname bị từ chối khi có allowlist); `name` mặc định.
5. **AuditRunService**: audit thành công (insecure → 8 FAIL, secure → 8 PASS) được lưu và đọc lại; lỗi kết nối → run FAILED có `error_code`; thiếu device → `DeviceNotFoundError`; thiếu credentials (không tham số, không mặc định) → `CredentialsRequiredError`; dùng credentials mặc định khi không truyền; **chạy song song cùng thiết bị** (connector giả chặn bằng `threading.Event`) → lần gọi thứ hai `AuditAlreadyRunningError`, hai thiết bị khác nhau không chặn nhau; khóa được nhả sau lỗi.
6. **Config**: `from_env` đủ/thiếu/không hợp lệ (API key ngắn, CIDR sai); `auth_disabled`; `repr(Settings)` không chứa API key.
7. **API – Auth**: không key/sai key → 401 trên mọi route trừ `/health`; key đúng → 200; `auth_disabled=True` bỏ qua; so sánh bằng `compare_digest` (kiểm tra mã nguồn bằng test hoặc review).
8. **API – Devices**: CRUD đầy đủ, mã trạng thái đúng, `latest_audit` null rồi có giá trị sau khi audit; 404/409/422; `extra` field bị từ chối; `device_id`/`host`/`port` sai bị 422 (gồm `../etc/passwd`, `host` có khoảng trắng hoặc `/`).
9. **API – Audits**: audit bằng credentials trong body và bằng biến môi trường; thiết bị lỗi kết nối (`fail_on`) → 201 + `status=FAILED` + `error_code`; 404 device/run; 409 khi đang chạy; lọc `status`/`severity` đúng, giá trị lọc sai → 422; phân trang.
10. **API – Bảo mật** (`test_security_api.py`):
    - Gửi body sai (thiếu `username`, thừa trường lạ) kèm `password="FAKE-API-PW"` → response 422 **không chứa** `FAKE-API-PW` và không có khóa `input`.
    - Chạy audit với password giả: `FAKE-API-PW`, enable secret `FAKE-API-ENABLE`, API key `FAKE-API-KEY-0123456789`: assert các chuỗi này **không xuất hiện** trong response JSON (mọi endpoint), trong `caplog` (mức DEBUG), trong **nội dung file SQLite** (đọc bytes cả `.db`, `-wal`), và trong `repr` của các schema/Settings.
    - Chuỗi bí mật giả trong `ios_insecure.cfg` (`FAKE-ENABLE-PW`, `FAKE-USER-PW`, `FAKE-COMMUNITY-RW`) không xuất hiện trong response, DB hay log.
    - Lỗi 500 (cho `AuditService` ném lỗi bất thường) trả thông báo chung, không lộ chi tiết.
    - CORS: không có header `access-control-allow-origin` khi `cors_origins` rỗng; có đúng origin khi cấu hình.
11. **Kiến trúc**: cập nhật test `ast` theo mục 2 (sqlite3 chỉ trong `repositories`; fastapi/pydantic/starlette/uvicorn chỉ trong `api` và `main.py`; `services`/`api` tách lớp đúng; ràng buộc cũ giữ nguyên).
12. Toàn bộ 178 test cũ vẫn xanh; `pytest -q` mặc định vẫn bỏ qua test `live`.

---

## 9. Thứ tự thực hiện (dừng và chạy `pytest -q` sau mỗi bước)

1. **Chuẩn bị**: liệt kê file đã tồn tại + `wc -c` theo cây mục 3; kiểm tra các phụ thuộc mới (`fastapi`, `uvicorn[standard]`, `httpx`) cài được mà **không đổi** phiên bản `netmiko`/`paramiko` (`pip freeze` trước và sau, báo cáo nếu có thay đổi); cập nhật `requirements.txt` và `.gitignore`. Chạy `pytest -q` xác nhận 178 test xanh.
2. **Domain**: lỗi mới, `Device`, `AuditRunSummary`, `AuditRunDetail`, hai interface repository + test entity ngắn.
3. **Database + DeviceRepository** + test mục 8.1–8.2.
4. **AuditRepository** + test mục 8.3. **DỪNG LẠI (checkpoint)**: tóm tắt schema thực tế, cách xử lý transaction/kết nối, danh sách test; chờ người dùng duyệt trước khi làm tiếp.
5. **Services**: `DeviceService`, `AuditRunService` + test mục 8.4–8.5.
6. **Config** + `core/dependencies.py` + test mục 8.6.
7. **API**: schemas, error handlers (gồm ghi đè validation), routes, `create_app`, xác thực + test mục 8.7–8.10.
8. **Test kiến trúc** (mục 8.11) và chạy toàn bộ test.
9. **Tài liệu** `docs/api_and_persistence.md`: bảng endpoint, ví dụ `curl` đầy đủ (tạo thiết bị, audit bằng credentials trong body và bằng biến môi trường, xem kết quả), bảng biến môi trường, hướng dẫn chạy `uvicorn ... --factory --host 127.0.0.1`, cách truy cập từ máy khác bằng SSH tunnel (`ssh -L 8000:127.0.0.1:8000 user@server`), cảnh báo bảo mật (credentials trong body, chỉ bind localhost hoặc đặt sau firewall/reverse proxy TLS, đặt `NETSENTRY_ALLOWED_NETWORKS`), và ghi chú về venv paramiko đời cũ.
10. **Báo cáo cuối**: file tạo/sửa, kết quả `pytest -q` (tổng và số test mới), kết quả chạy thử API thật bằng `uvicorn` + `curl` với `FakeConnector` không áp dụng được ở đây nên chỉ kiểm tra `/health`, auth 401, tạo/liệt kê/xóa thiết bị; các điểm mơ hồ còn lại.

---

## 10. Tiêu chí hoàn thành

- [ ] `cd backend && pytest -q` xanh toàn bộ, gồm 178 test cũ.
- [ ] `uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000` khởi động được với `NETSENTRY_API_KEY` hợp lệ; thiếu key thì thoát với `ConfigError` rõ ràng.
- [ ] Mọi route (trừ `/health`) yêu cầu `X-API-Key`; so sánh hằng thời gian.
- [ ] Không tìm thấy password, enable secret, API key hay raw config trong: response, log, file SQLite, `repr` (có test tự động, kể cả khi request sai định dạng).
- [ ] Không lưu credential thiết bị vào database; schema không có cột tương ứng.
- [ ] Audit lỗi kết nối vẫn được lưu và trả 201 với `status=FAILED`.
- [ ] Không chạy được hai audit song song trên cùng một thiết bị (409).
- [ ] Mọi truy vấn SQL dùng tham số hóa; `sqlite3` chỉ trong `app/repositories/`; fastapi/pydantic chỉ trong `app/api/` và `app/main.py`.
- [ ] Phiên bản `netmiko`/`paramiko` trong venv không bị thay đổi.
- [ ] Không file nào ngoài phạm vi bị sửa/xóa (SSH cũ, placeholder khác).

---

## 11. Để giai đoạn sau (KHÔNG làm ở đây)

- Frontend (danh sách thiết bị, bảng findings, nút chạy audit) gọi API này.
- Route finding xuyên thiết bị, thống kê xu hướng điểm bảo mật.
- Snapshot + diff cấu hình (lúc đó mới lưu config đã che bí mật).
- AI giải thích finding (`AIProvider`/Ollama), chỉ nhận finding đã che bí mật.
- Remediation có phê duyệt; job chạy nền; xác thực người dùng thật.
