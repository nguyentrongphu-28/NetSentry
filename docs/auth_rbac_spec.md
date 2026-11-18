# NetSentry – Đặc tả Đăng nhập Web + Phân quyền (RBAC) + Vận hành qua Cloudflare Tunnel cho Antigravity

> Cách dùng: lưu vào `docs/auth_rbac_spec.md`, mở Antigravity ở chế độ **Planning**, gửi: *"Đọc @docs/auth_rbac_spec.md và thực hiện đúng từng bước ở mục 11. Đưa plan trước, đợi tôi duyệt rồi mới code. Không ghi đè file không rỗng mà chưa hỏi."*
> Quy ước ngôn ngữ: giải thích bằng tiếng Việt; tên file/class/hàm/biến, docstring, comment, thông báo lỗi và mô tả API viết bằng tiếng Anh; **chữ hiển thị trên giao diện viết bằng tiếng Việt** (gom vào file chuỗi hiện có `strings.ts`).
> Điều kiện đầu vào: backend (Rule Engine, Connector, AuditService, SQLite, REST API) và frontend dashboard đã xong, đã commit, test đang xanh, và **lỗi mất focus trong `Modal`/`AddDeviceDialog` đã được sửa** (effect focus-trap chỉ phụ thuộc `open`, không phụ thuộc `onClose`). **Hãy tạo branch mới `feat/auth-rbac` trước khi bắt đầu.**

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư full-stack senior, chuyên bảo mật ứng dụng web. Hãy thêm **đăng nhập bằng tài khoản + phân quyền 3 vai trò** vào NetSentry và chuẩn bị cho việc **demo công khai qua Cloudflare Quick Tunnel**, đồng thời giữ cho việc nâng cấp sang Named Tunnel + domain riêng sau này **không phải sửa code**.

Quy tắc bắt buộc:

1. Làm đúng thứ tự mục 11. Sau mỗi bước chạy `pytest -q` (từ `backend/`) và, với bước frontend, `npm run lint`, `npm run typecheck`, `npm test`. Chỉ đi tiếp khi xanh. **Toàn bộ test hiện có (backend và frontend) phải tiếp tục xanh.**
2. Không thêm tính năng ngoài phạm vi (mục 1). Đặc tả mơ hồ hoặc mâu thuẫn → **dừng lại và hỏi**.
3. Unit/API test **không** mở kết nối mạng thật; dùng `FakeConnector`. Không đổi test `live`.
4. Không sửa logic Rule Engine, parser, rule, `CiscoIOSConnector`, `AuditService`, `AuditRunService`, `DeviceService`. Chỉ được **thêm**. Sửa file hiện có chỉ ở các điểm mục 3 liệt kê rõ ("SỬA"); ngoài đó thì hỏi.
5. **Không đụng vào phiên bản `netmiko` và `paramiko`.** Thư viện mới thêm vào (chỉ `argon2-cffi`, mục 2) không được kéo nâng/hạ hai gói này; kiểm tra bằng `pip freeze` trước/sau.
6. Python 3.11+, type hints đầy đủ. Frontend TypeScript `strict`, không `any`.
7. **Không bao giờ lưu, log, trả về, đưa vào lỗi hay vào `security_events`**: mật khẩu (kể cả mật khẩu sai khi đăng nhập), session token thô, SSH credentials, API key, raw running-config.
8. Trước khi tạo file, liệt kê file đã có trong cây thư mục mục 3 kèm `wc -c`. File **0 byte** được ghi đè; file **không rỗng** thì hỏi trước.
9. **Không đoán** hình dạng code hiện có. Trước khi sửa frontend, đọc `frontend/src/api/*`, `frontend/src/app/*`, `Modal.tsx`, `RunAuditDialog.tsx`; trước khi sửa backend, đọc `app/main.py`, `app/core/config.py`, `app/api/*`. Sai khác giữa đặc tả này và code thật → code thật là chuẩn, ghi sai khác vào báo cáo.

---

## 1. Phạm vi

**Làm**

- Tài khoản người dùng (SQLite), băm mật khẩu **argon2id**.
- Đăng nhập/đăng xuất bằng **session cookie** (`HttpOnly`, `Secure`, `SameSite=Strict`), token phiên lưu **dạng băm** trong SQLite (dễ thu hồi).
- 3 vai trò `admin`, `operator`, `viewer` và ma trận quyền (mục 5), áp dụng **ở backend** cho mọi route hiện có.
- Chống brute-force: khóa tài khoản tạm thời + giới hạn tốc độ theo IP.
- Bảo vệ CSRF (kiểm tra `Origin` + `SameSite`), header bảo mật, kiểm tra `Host`.
- Bắt buộc đổi mật khẩu lần đầu; quản lý người dùng (chỉ admin); nhật ký sự kiện bảo mật (`security_events`).
- **Chế độ công khai** `NETSENTRY_PUBLIC_MODE=1` (mục 7) dùng khi chạy qua tunnel.
- Backend **phục vụ luôn bản build frontend** cùng origin (để cookie + CSRF đơn giản, URL tunnel đổi không vỡ gì).
- Frontend: trang đăng nhập, route guard, đổi mật khẩu bắt buộc, ẩn/vô hiệu nút theo quyền, trang quản lý người dùng và trang nhật ký bảo mật (admin).
- CLI tạo admin đầu tiên / đặt lại mật khẩu.
- Test đầy đủ, tài liệu `docs/auth_and_deploy.md` (gồm 2 checklist vận hành: demo và dài hạn).

**KHÔNG làm** (để giai đoạn sau, mục 13)

- MFA/TOTP, SSO/OAuth, đăng nhập bằng Google, quên mật khẩu qua email, tự đăng ký tài khoản.
- Quyền theo từng thiết bị (ACL theo device), nhiều tổ chức (multi-tenant).
- Redis/hàng đợi; rate-limit chạy trong bộ nhớ của một tiến trình là đủ.
- Tích hợp Cloudflare Access (chỉ chừa điểm mở rộng, mục 8.4).
- Lưu credential thiết bị vào database (**vẫn cấm tuyệt đối**).
- Docker, systemd unit (chỉ viết hướng dẫn trong tài liệu).

---

## 2. Ràng buộc kiến trúc và phụ thuộc

- `app/domain/`: chỉ thư viện chuẩn. Thêm entity `User`, `Role`, `SecurityEvent` và lỗi mới.
- `sqlite3` chỉ trong `app/repositories/`.
- `argon2` chỉ được import trong `app/security/password_hasher.py` (hoặc `app/services/` nếu hiện có quy ước khác; hỏi nếu mâu thuẫn). Mọi nơi khác dùng interface `PasswordHasher`.
- `fastapi`, `pydantic`, `starlette`, `uvicorn` chỉ trong `app/api/` và `app/main.py`.
- `services` phụ thuộc **interface** (repository, `PasswordHasher`, `Clock`, `TokenGenerator`), nhận qua constructor (DI). `api` chỉ gọi `services`.
- Cập nhật `tests/unit/test_architecture_imports.py` (dùng `ast`) để thực thi các ràng buộc trên.
- **Phụ thuộc mới duy nhất:** `argon2-cffi`, ghim phiên bản chính xác, chọn bản đã phát hành **≥ 14 ngày**, kiểm tra không kéo đổi `paramiko`/`netmiko`. Không thêm thư viện JWT/OAuth/session ngoài. Frontend: **không thêm phụ thuộc mới**.
- Sinh token bằng `secrets.token_urlsafe(32)`; so sánh bằng `secrets.compare_digest`/`hmac.compare_digest`; băm token phiên bằng SHA-256 trước khi lưu (token có entropy cao nên SHA-256 là đủ).

---

## 3. Cây thư mục (chỉ file thuộc giai đoạn này)

```
backend/
  app/
    domain/
      errors.py                     # SỬA: chỉ THÊM lỗi mới (mục 4.1)
      entities/
        user.py                     # User, Role
        security_event.py           # SecurityEvent, SecurityEventType
      repositories_iface.py (hoặc tương đương hiện có)  # SỬA: THÊM UserRepository, SessionRepository, SecurityEventRepository
    security/
      __init__.py
      password_hasher.py            # PasswordHasher (Protocol) + Argon2PasswordHasher
      password_policy.py            # validate_password_strength()
      rate_limiter.py               # InMemorySlidingWindowLimiter
      tokens.py                     # TokenGenerator, hash_token()
      client_ip.py                  # resolve_client_ip()
    repositories/
      database.py                   # SỬA: SCHEMA v2 (mục 6), user_version = 2
      sqlite_user_repository.py
      sqlite_session_repository.py
      sqlite_security_event_repository.py
    services/
      auth_service.py               # AuthService
      user_service.py               # UserService
      security_event_service.py     # SecurityEventService
    api/
      deps.py                       # SỬA: thêm get_current_principal, require_role, require_same_origin
      middleware.py                 # security headers, origin check, trusted host
      routes/
        auth.py                     # /auth/*
        users.py                    # /users/*  (admin)
        security_events.py          # /security-events (admin)
        devices.py, audits.py       # SỬA: gắn require_role + ghi security_event (mục 5.2)
      schemas/
        auth.py, users.py, security_events.py
      static.py                     # phục vụ frontend/dist + SPA fallback
    core/
      config.py                     # SỬA: thêm biến môi trường mục 7
    main.py                         # SỬA: create_app gắn middleware, router, static
  scripts/
    create_admin.py                 # tạo admin đầu tiên (getpass)
    reset_password.py               # đặt lại mật khẩu 1 user (getpass)
  tests/
    unit/ ... (mục 9)
frontend/
  src/
    auth/
      AuthProvider.tsx, useAuth.ts, RequireAuth.tsx, RequireRole.tsx, useCan.ts
    pages/
      LoginPage.tsx, ChangePasswordPage.tsx, UsersPage.tsx, SecurityEventsPage.tsx
    components/users/               # CreateUserDialog, EditUserDialog, ResetPasswordDialog
    api/                            # SỬA: client dùng cookie, bỏ API key (mục 10)
docs/
  auth_and_deploy.md
```

---

## 4. Đặc tả domain

### 4.1 Lỗi mới (`domain/errors.py`, chỉ thêm)

```python
class InvalidCredentialsError(NetSentryError):      code = "INVALID_CREDENTIALS"      # 401
class AccountLockedError(NetSentryError):           code = "ACCOUNT_LOCKED"           # 429
class RateLimitedError(NetSentryError):             code = "RATE_LIMITED"             # 429 (+ Retry-After)
class NotAuthenticatedError(NetSentryError):        code = "UNAUTHORIZED"             # 401 (giữ mã cũ)
class ForbiddenError(NetSentryError):               code = "FORBIDDEN"                # 403
class PasswordChangeRequiredError(NetSentryError):  code = "PASSWORD_CHANGE_REQUIRED" # 403
class WeakPasswordError(NetSentryError):            code = "WEAK_PASSWORD"            # 422
class UserExistsError(NetSentryError):              code = "USER_EXISTS"              # 409
class UserNotFoundError(NetSentryError):            code = "USER_NOT_FOUND"           # 404
class LastAdminError(NetSentryError):               code = "LAST_ADMIN"               # 409
class OriginNotAllowedError(NetSentryError):        code = "ORIGIN_NOT_ALLOWED"       # 403
class BodyCredentialsDisabledError(NetSentryError): code = "BODY_CREDENTIALS_DISABLED"# 422
```

### 4.2 Entity

```python
class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

@dataclass(frozen=True)
class User:
    id: int
    username: str                 # ^[a-z0-9][a-z0-9._-]{2,31}$, lưu dạng chữ thường
    role: Role
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None
    # KHÔNG chứa password_hash trong entity trả ra ngoài; hash chỉ nằm trong
    # lớp record nội bộ của repository (UserWithHash) dùng cho AuthService.

class SecurityEventType(str, Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_LOCKED = "LOGIN_LOCKED"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET = "PASSWORD_RESET"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    DEVICE_CREATED = "DEVICE_CREATED"
    DEVICE_DELETED = "DEVICE_DELETED"
    AUDIT_STARTED = "AUDIT_STARTED"
    ACCESS_DENIED = "ACCESS_DENIED"
```

`SecurityEvent`: `id`, `occurred_at`, `event_type`, `actor_username: str | None`, `client_ip: str | None`, `target: str | None` (vd `device_id`, `username`, `run_id`), `detail: str | None` (≤ 200 ký tự, **không chứa bí mật**).

### 4.3 Interface repository (thêm)

- `UserRepository`: `add`, `get_by_id`, `get_by_username` (trả `UserWithHash`), `list`, `update_role_active`, `update_password(user_id, hash, must_change)`, `record_login_success(user_id, at)`, `register_failed_attempt(user_id, at, max_attempts, lock_minutes)`, `count_active_admins()`.
- `SessionRepository`: `create(token_hash, user_id, created_at, expires_at, client_ip, user_agent_trunc)`, `get_valid(token_hash, now, idle_minutes)` (trả user + session), `touch(token_hash, now)`, `delete(token_hash)`, `delete_all_for_user(user_id, except_token_hash=None)`, `purge_expired(now)`.
- `SecurityEventRepository`: `add`, `list(limit, before_id, event_type=None)`.

---

## 5. Phân quyền (RBAC)

### 5.1 Ma trận quyền

| Hành động / Endpoint | viewer | operator | admin |
|---|:-:|:-:|:-:|
| `GET /health` (công khai) | ✔ | ✔ | ✔ |
| `GET /auth/me`, `POST /auth/logout`, `POST /auth/change-password` | ✔ | ✔ | ✔ |
| Xem thiết bị, danh sách audit, chi tiết audit, findings (mọi `GET /devices*`, `GET /audits*`) | ✔ | ✔ | ✔ |
| `POST /devices` (thêm thiết bị) | ✘ | ✔ | ✔ |
| `POST /devices/{id}/audit` (chạy audit) | ✘ | ✔ | ✔ |
| `DELETE /devices/{id}` | ✘ | ✘ | ✔ |
| `/users/*` (xem, tạo, sửa quyền/khóa, đặt lại mật khẩu) | ✘ | ✘ | ✔ |
| `GET /security-events` | ✘ | ✘ | ✔ |

Thiếu đăng nhập → `401 UNAUTHORIZED`. Đủ đăng nhập nhưng thiếu quyền → `403 FORBIDDEN` và ghi `ACCESS_DENIED` (kèm endpoint, không kèm body).

### 5.2 Cách thực thi

- Dependency `require_role(*roles: Role)` ở `api/deps.py`; **mọi** route (trừ `/health`, `/auth/login`) phải có dependency xác thực. Viết test **tự động duyệt toàn bộ route của `app.routes`** và khẳng định không route nào (ngoài whitelist `{"/health", "/api/v1/auth/login"}` và file tĩnh) truy cập được khi chưa đăng nhập. Test này chặn trường hợp quên gắn quyền cho route mới.
- Khi `must_change_password=True`: mọi route trừ `GET /auth/me`, `POST /auth/logout`, `POST /auth/change-password` trả `403 PASSWORD_CHANGE_REQUIRED`.
- Ghi `security_events` (qua `SecurityEventService`, được tiêm vào route hoặc gọi trong service) cho: `DEVICE_CREATED`, `DEVICE_DELETED`, `AUDIT_STARTED` (target = `device_id`, detail = `run_id` khi có). **Không sửa** `DeviceService`/`AuditRunService`; ghi sự kiện ở tầng route (hoặc một lớp bọc mỏng trong `api/`) sau khi service thành công.
- Frontend ẩn/vô hiệu nút theo quyền chỉ để **thân thiện**; backend mới là nơi chặn thật.

### 5.3 Principal

`Principal = (user: User | None, kind: "session" | "api_key" | "disabled")`.

- `session`: người dùng đăng nhập bình thường.
- `api_key`: header `X-API-Key` đúng → principal vai trò `admin`, `username="api-key"`. **Chỉ hoạt động khi `NETSENTRY_API_KEY_AUTH=1`** và **không** ở chế độ công khai (mục 7). Dùng cho script/CI cục bộ và để các test API hiện có không phải viết lại.
- `disabled`: `NETSENTRY_AUTH_DISABLED=1` (chỉ dev) → principal admin giả. **Ở chế độ công khai, bật cờ này phải làm app từ chối khởi động** (`RuntimeError`).

---

## 6. Đặc tả lưu trữ SQLite (schema v2)

`init_db` idempotent. Nâng `PRAGMA user_version` từ 1 → 2 bằng `CREATE TABLE IF NOT EXISTS` (không đụng bảng cũ). `user_version` lớn hơn code biết → `RuntimeError` như cũ.

```sql
CREATE TABLE IF NOT EXISTS users (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  username              TEXT NOT NULL UNIQUE,
  password_hash         TEXT NOT NULL,
  role                  TEXT NOT NULL CHECK (role IN ('admin','operator','viewer')),
  is_active             INTEGER NOT NULL DEFAULT 1,
  must_change_password  INTEGER NOT NULL DEFAULT 1,
  failed_attempts       INTEGER NOT NULL DEFAULT 0,
  locked_until          TEXT,                 -- ISO-8601 UTC
  created_at            TEXT NOT NULL,
  last_login_at         TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash   TEXT PRIMARY KEY,              -- SHA-256 hex của token thô
  user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at   TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at   TEXT NOT NULL,
  client_ip    TEXT,
  user_agent   TEXT                           -- cắt tối đa 200 ký tự
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS security_events (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at    TEXT NOT NULL,
  event_type     TEXT NOT NULL,
  actor_username TEXT,
  client_ip      TEXT,
  target         TEXT,
  detail         TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_time ON security_events(occurred_at DESC);
```

- Mọi truy vấn **tham số hóa**. `PRAGMA foreign_keys=ON` (đã có).
- `security_events` giữ tối đa 90 ngày hoặc 10 000 dòng; dọn khi khởi động (`purge`), không dùng tác vụ nền.
- Quyền file DB: nếu hệ điều hành là POSIX, `chmod 0o600` cho file DB khi tạo mới (DB nay chứa hash mật khẩu).

---

## 7. Cấu hình (`core/config.py`)

Biến **mới** (biến cũ giữ nguyên):

| Biến | Mặc định | Mô tả |
|---|---|---|
| `NETSENTRY_PUBLIC_MODE` | `0` | `1` = chế độ công khai (qua tunnel). Hiệu ứng ở bảng dưới. |
| `NETSENTRY_API_KEY_AUTH` | `1` | Cho phép đăng nhập bằng header `X-API-Key` (principal admin). Bị **ép về 0** khi `PUBLIC_MODE=1`. |
| `NETSENTRY_SESSION_COOKIE_SECURE` | `1` | Cờ `Secure` của cookie. Dev http local đặt `0`. Bị **ép về 1** khi `PUBLIC_MODE=1`. |
| `NETSENTRY_SESSION_TTL_MINUTES` | `480` | Hạn tuyệt đối của phiên (8 giờ). |
| `NETSENTRY_SESSION_IDLE_MINUTES` | `30` | Không hoạt động quá ngưỡng này thì phiên hết hạn. |
| `NETSENTRY_MAX_FAILED_LOGINS` | `5` | Số lần sai liên tiếp trước khi khóa tài khoản. |
| `NETSENTRY_LOCKOUT_MINUTES` | `15` | Thời gian khóa. |
| `NETSENTRY_LOGIN_RATE_LIMIT` | `10/300` | Tối đa 10 lần đăng nhập mỗi 300 giây **theo IP**. |
| `NETSENTRY_TRUSTED_IP_HEADER` | rỗng | Vd `CF-Connecting-IP`. Chỉ được tin khi kết nối trực tiếp đến từ loopback (`127.0.0.1`/`::1`), tức là từ `cloudflared`. |
| `NETSENTRY_ALLOWED_HOSTS` | `localhost,127.0.0.1,*.trycloudflare.com` | Danh sách `Host` hợp lệ (hỗ trợ `*.` đầu). Giai đoạn 2 thêm domain riêng. |
| `NETSENTRY_ALLOW_BODY_CREDENTIALS` | `1` | Cho phép client gửi `credentials` trong body audit. Bị **ép về 0** khi `PUBLIC_MODE=1`. |
| `NETSENTRY_SERVE_FRONTEND` | `0` | `1` = phục vụ `frontend/dist` tại `/` với SPA fallback. |
| `NETSENTRY_FRONTEND_DIST` | `<repo>/frontend/dist` | Đường dẫn bản build. |

**Hiệu ứng của `NETSENTRY_PUBLIC_MODE=1`** (tất cả kiểm tra khi khởi động, vi phạm → log lỗi rõ ràng và dừng):

1. Tắt xác thực bằng API key; **từ chối khởi động** nếu `NETSENTRY_AUTH_DISABLED=1`.
2. Ép cookie `Secure`, ép `NETSENTRY_ENABLE_DOCS=0` (`/docs`, `/redoc`, `/openapi.json` đều 404).
3. Ép `ALLOW_BODY_CREDENTIALS=0`: body audit có `credentials` → `422 BODY_CREDENTIALS_DISABLED`. Server **bắt buộc** dùng `NETSENTRY_SSH_USERNAME/PASSWORD/ENABLE_SECRET` từ môi trường; thiếu → vẫn trả `CREDENTIALS_REQUIRED` như cũ.
4. **Từ chối khởi động nếu `NETSENTRY_ALLOWED_NETWORKS` rỗng** (chống SSRF, mục tiêu thiết bị chỉ trong dải lab).
5. **Từ chối khởi động nếu chưa có người dùng admin nào** (buộc chạy `scripts/create_admin.py` trước).
6. Bật `TrustedHostMiddleware` theo `NETSENTRY_ALLOWED_HOSTS`; `NETSENTRY_SERVE_FRONTEND` nên bằng `1` (cảnh báo nếu `0`).

Bind vẫn là `127.0.0.1` (xem mục 12); app **không** tự bind `0.0.0.0`.

---

## 8. Đặc tả dịch vụ và API

### 8.1 Mật khẩu và đăng nhập

- `Argon2PasswordHasher`: argon2id, tham số mặc định an toàn của `argon2-cffi` (`PasswordHasher()`); có `verify` và `needs_rehash` (nếu cần rehash thì cập nhật hash sau đăng nhập thành công).
- `validate_password_strength(password, username)`: độ dài **12–128**, khác `username`, không nằm trong một danh sách ngắn mật khẩu phổ biến nhúng sẵn (~50 mục như `password1234`, `admin123456`, `netsentry123`…), không toàn một loại ký tự lặp. Sai → `WeakPasswordError` với thông báo nêu **quy tắc**, không nêu mật khẩu.
- `AuthService.login(username, password, client_ip, user_agent)`:
  1. Kiểm tra rate limit theo IP trước → `RateLimitedError` (kèm `retry_after`).
  2. Tìm user theo `username` (chuẩn hóa chữ thường). **Nếu không tồn tại: vẫn thực hiện một lần `verify` với hash giả** để thời gian phản hồi gần bằng nhau, rồi trả `InvalidCredentialsError`.
  3. User bị khóa (`locked_until > now`) → `AccountLockedError`. User `is_active=0` → `InvalidCredentialsError` (cùng thông báo chung).
  4. Sai mật khẩu → tăng `failed_attempts`; đạt `MAX_FAILED_LOGINS` thì đặt `locked_until = now + LOCKOUT_MINUTES` và ghi `LOGIN_LOCKED`; luôn trả `InvalidCredentialsError("Invalid username or password")`.
  5. Đúng → reset `failed_attempts`, cập nhật `last_login_at`, tạo phiên mới (token thô trả về một lần, lưu SHA-256), ghi `LOGIN_SUCCESS`.
  6. Chống session fixation: luôn tạo token mới, không tái sử dụng token gửi kèm.
- Thông báo lỗi đăng nhập **luôn** là `"Invalid username or password"`, không phân biệt user không tồn tại / sai mật khẩu / bị vô hiệu.
- Đổi mật khẩu: yêu cầu `current_password` đúng; mật khẩu mới qua policy và khác mật khẩu cũ; thành công → `must_change_password=0`, **thu hồi mọi phiên khác** của user (giữ phiên hiện tại), ghi `PASSWORD_CHANGED`.
- Admin đặt lại mật khẩu user khác → `must_change_password=1`, thu hồi mọi phiên của user đó, ghi `PASSWORD_RESET`.
- Đổi vai trò hoặc vô hiệu hóa user → thu hồi mọi phiên của user đó, ghi `USER_UPDATED`.
- **Bảo vệ admin cuối cùng:** không cho vô hiệu hóa hoặc hạ quyền admin nếu sau thao tác không còn admin hoạt động nào → `LastAdminError`.

### 8.2 Phiên và cookie

- Cookie `netsentry_session`: `HttpOnly`, `SameSite=Strict`, `Path=/`, `Secure` theo cấu hình, `Max-Age` = TTL. Không đặt `Domain` (chỉ host hiện tại).
- Phiên hợp lệ khi: chưa quá `expires_at`, `now - last_seen_at ≤ IDLE_MINUTES`, user `is_active`. Mỗi request hợp lệ cập nhật `last_seen_at` (tối đa 1 lần/phút để giảm ghi DB).
- Đăng xuất: xóa phiên trong DB + trả `Set-Cookie` hết hạn.
- Khi khởi động: `purge_expired`.

### 8.3 Endpoint (`/api/v1`)

| Phương thức | Đường dẫn | Quyền | Mô tả | Thành công | Lỗi |
|---|---|---|---|---|---|
| `POST` | `/auth/login` | công khai | Body `{username, password}`; đặt cookie | `200` + `{user}` | `401`, `422`, `429` |
| `POST` | `/auth/logout` | đã đăng nhập | Xóa phiên | `204` | `401` |
| `GET` | `/auth/me` | đã đăng nhập | Người dùng hiện tại + `capabilities` | `200` | `401` |
| `POST` | `/auth/change-password` | đã đăng nhập | `{current_password, new_password}` | `204` | `401`, `422` |
| `GET` | `/users` | admin | Danh sách người dùng | `200` | `401`, `403` |
| `POST` | `/users` | admin | `{username, password, role}`; `must_change_password=1` | `201` | `401`, `403`, `409`, `422` |
| `PATCH` | `/users/{id}` | admin | `{role?, is_active?}` | `200` | `401`, `403`, `404`, `409` |
| `POST` | `/users/{id}/reset-password` | admin | `{new_password}` | `204` | `401`, `403`, `404`, `422` |
| `GET` | `/security-events` | admin | `?limit=50&before_id=&event_type=` (limit tối đa 200) | `200` | `401`, `403`, `422` |

`GET /auth/me` trả:

```json
{
  "user": {"id": 1, "username": "alice", "role": "operator", "must_change_password": false},
  "capabilities": {"body_credentials": false}
}
```

`capabilities.body_credentials` cho frontend biết có hiển thị ô nhập credentials trong `RunAuditDialog` hay không (mục 10). **Không bao giờ trả `password_hash`, token, `failed_attempts`** trong bất kỳ response nào.

Mã lỗi giữ nguyên dạng `{"error": {"code": "...", "message": "..."}}`; handler `RequestValidationError` (đã loại `input`) áp dụng cho cả endpoint mới, **đặc biệt** `/auth/login`, `/auth/change-password`, `/users` (nơi có mật khẩu trong body).

### 8.4 Điểm mở rộng cho Cloudflare Access (giai đoạn 2, **chưa làm**)

Đặt việc xác định người dùng sau một hàm `resolve_principal(request) -> Principal | None` trong `api/deps.py`, gọi lần lượt các "nguồn" (session cookie → API key). Về sau chỉ cần thêm một nguồn đọc header `Cf-Access-Authenticated-User-Email` (đã được Cloudflare ký/kiểm chứng) mà không viết lại RBAC. Hiện tại **không** đọc header đó.

### 8.5 CSRF, Origin, Host, header bảo mật (`api/middleware.py`)

- **Kiểm tra Origin** cho mọi method thay đổi dữ liệu (`POST/PUT/PATCH/DELETE`) khi có cookie phiên: header `Origin` (hoặc `Referer` nếu thiếu `Origin`) phải có `netloc` **bằng header `Host`** của request, hoặc nằm trong `NETSENTRY_CORS_ORIGINS`. Thiếu cả hai → `403 ORIGIN_NOT_ALLOWED`. (Cách này không cần biết trước URL tunnel ngẫu nhiên.) `POST /auth/login` cũng kiểm tra.
- `TrustedHostMiddleware` theo `NETSENTRY_ALLOWED_HOSTS` (luôn bật ở chế độ công khai; ở dev mặc định cho phép `localhost`, `127.0.0.1`).
- Header cho mọi response:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: geolocation=(), camera=(), microphone=()`
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` (nếu bản build Vite cần nới `style-src`, ghi vào báo cáo; **không** cho `unsafe-eval`).
  - `Cache-Control: no-store` cho mọi response dưới `/api/`.
- CORS: giữ cơ chế `NETSENTRY_CORS_ORIGINS` hiện có; vì phục vụ cùng origin nên ở chế độ công khai **để trống** là bình thường. Không bao giờ dùng `*` cùng `allow_credentials`.

### 8.6 IP người dùng và giới hạn tốc độ

- `resolve_client_ip(request)`: nếu `NETSENTRY_TRUSTED_IP_HEADER` được đặt **và** địa chỉ kết nối trực tiếp (`request.client.host`) là loopback → dùng giá trị header (lấy phần tử đầu, kiểm tra là IP hợp lệ bằng `ipaddress`, sai định dạng thì rơi về địa chỉ kết nối). Ngược lại dùng `request.client.host`. **Không bao giờ** tin header khi kết nối không đến từ loopback (chống giả mạo IP).
- `InMemorySlidingWindowLimiter(max, window_seconds)` an toàn đa luồng (khóa `threading.Lock`), dọn khóa cũ; áp dụng cho `/auth/login` theo IP. Ghi rõ trong tài liệu: giới hạn nằm trong bộ nhớ một tiến trình, mất khi restart.

### 8.7 Phục vụ frontend (`api/static.py`)

- Khi `NETSENTRY_SERVE_FRONTEND=1` và thư mục dist tồn tại: phục vụ file tĩnh tại `/`, và mọi đường dẫn **không** bắt đầu bằng `/api/` hoặc `/health` mà không khớp file thì trả `index.html` (SPA fallback). Chống path traversal (dùng `StaticFiles`, không tự nối chuỗi đường dẫn). `/api/*` không tồn tại → vẫn 404 JSON, không rơi vào fallback.
- Đây là **ngoại lệ có chủ đích** so với `frontend_spec.md` (trước đây không phục vụ bản build từ FastAPI). Không sửa file `frontend_spec.md`.

### 8.8 CLI

- `scripts/create_admin.py --username NAME`: đọc mật khẩu bằng `getpass` (xác nhận 2 lần), qua `validate_password_strength`, tạo user `admin` với `must_change_password=1`. **Không nhận mật khẩu qua tham số dòng lệnh hay biến môi trường.** Mã thoát: `0` thành công, `1` lỗi đầu vào/mật khẩu yếu, `2` user đã tồn tại.
- `scripts/reset_password.py --username NAME`: tương tự, đặt `must_change_password=1`, thu hồi mọi phiên.

---

## 9. Yêu cầu test

Dùng `FakeConnector`, DB SQLite tạm (`tmp_path`), `Clock` giả để điều khiển thời gian. Không mạng thật.

1. **Password policy & hasher**: các ca hợp lệ/không hợp lệ; hash khác nhau cho cùng mật khẩu (salt); `verify` đúng/sai; `needs_rehash`.
2. **UserRepository / SessionRepository / SecurityEventRepository** (SQLite thật, tạm): CRUD, `UNIQUE username`, cascade xóa phiên khi xóa user, `purge_expired`, đếm admin hoạt động, truy vấn tham số hóa (thử `username` chứa `'; DROP TABLE users;--` không gây hại).
3. **AuthService**: đăng nhập đúng/sai; thông báo lỗi **giống hệt** cho user không tồn tại và sai mật khẩu; khóa sau N lần sai và tự mở khóa sau `LOCKOUT_MINUTES`; đăng nhập đúng reset bộ đếm; user vô hiệu không đăng nhập được; hết hạn tuyệt đối và hết hạn do idle; đổi mật khẩu thu hồi phiên khác nhưng giữ phiên hiện tại; reset mật khẩu bắt đổi lần sau; **token thô không bao giờ xuất hiện trong DB** (chỉ SHA-256).
4. **UserService**: tạo user (trùng → `USER_EXISTS`), đổi vai trò, vô hiệu hóa thu hồi phiên, **`LAST_ADMIN`** khi hạ quyền/vô hiệu admin cuối (kể cả tự thao tác trên chính mình).
5. **Rate limiter & client IP**: cửa sổ trượt đúng; **tin `CF-Connecting-IP` khi kết nối từ loopback, bỏ qua header khi kết nối từ IP khác**; header sai định dạng bị bỏ qua.
6. **API – Auth**: đăng nhập đặt cookie với đủ cờ (`HttpOnly`, `SameSite=Strict`, `Secure` theo cấu hình); `GET /auth/me`; logout xóa phiên (dùng lại cookie cũ → 401); phiên hết hạn → 401; `must_change_password` chặn mọi route khác bằng `403 PASSWORD_CHANGE_REQUIRED`; 429 kèm `Retry-After`.
7. **API – RBAC (ma trận đầy đủ)**: tham số hóa **mỗi vai trò × mỗi endpoint** theo bảng 5.1, khẳng định đúng 200/201/204 hoặc 403; chưa đăng nhập → 401. **Test duyệt toàn bộ `app.routes`** theo mục 5.2.
8. **API – Bảo mật**: Origin sai → 403 `ORIGIN_NOT_ALLOWED`; Origin khớp Host → qua; thiếu Origin/Referer ở POST có cookie → 403; Host lạ → 400 từ `TrustedHostMiddleware`; header bảo mật có mặt; `Cache-Control: no-store` ở `/api/`; lỗi validation ở `/auth/login`, `/auth/change-password`, `/users` **không chứa** mật khẩu đã gửi (assert chuỗi mật khẩu thử nghiệm không xuất hiện trong body response, log, và `security_events`).
9. **API – Chế độ công khai**: khởi động bị từ chối khi thiếu `ALLOWED_NETWORKS`, thiếu admin, hoặc `AUTH_DISABLED=1`; API key bị từ chối; `/docs` và `/openapi.json` → 404; body audit có `credentials` → `422 BODY_CREDENTIALS_DISABLED`; audit dùng credentials môi trường thành công (FakeConnector).
10. **Security events**: mỗi hành động ở mục 5.2 sinh đúng sự kiện; `GET /security-events` chỉ admin; lọc `event_type`, phân trang; **không** sự kiện nào chứa mật khẩu/token.
11. **Static/SPA**: `/` trả `index.html`; `/devices/abc` trả `index.html`; `/api/v1/khong-ton-tai` trả 404 JSON; thử path traversal (`/..%2f..%2fetc/passwd`) không đọc được file ngoài dist.
12. **Frontend (Vitest + Testing Library + MSW)**:
    - `LoginPage`: gửi đúng, hiện lỗi chung khi 401, hiện thông báo khóa/rate-limit khi 429, **không** lưu mật khẩu ở bất kỳ storage nào.
    - `RequireAuth`: chưa đăng nhập → chuyển `/login`; `PASSWORD_CHANGE_REQUIRED` → chuyển `/change-password`.
    - `RequireRole`/`useCan`: `viewer` không thấy nút Thêm/Xóa/Chạy audit; `operator` thấy Thêm/Chạy audit nhưng không thấy Xóa; `admin` thấy tất cả và có menu Người dùng, Nhật ký bảo mật.
    - Khi API trả 401 giữa phiên → trạng thái đăng xuất + chuyển về `/login` kèm thông báo "Phiên đã hết hạn".
    - `RunAuditDialog`: ẩn ô credentials khi `capabilities.body_credentials=false`, và body gửi đi là `{}`.
    - `AddDeviceDialog`/`Modal`: **test hồi quy lỗi focus** (gõ nhiều ký tự liên tiếp, `document.activeElement` vẫn là ô nhập).
    - `UsersPage`: tạo user, đổi vai trò, vô hiệu hóa, đặt lại mật khẩu, hiển thị lỗi `LAST_ADMIN`.
13. **Kiến trúc**: cập nhật `test_architecture_imports.py` theo mục 2; test kiểm tra không có chuỗi `localStorage`/`sessionStorage` chứa `password`/`token`/`apiKey` trong `frontend/src` (grep trong test hoặc lint rule).

---

## 10. Đặc tả frontend

Đọc code hiện có trước (quy tắc 9). Yêu cầu:

- **Bỏ màn hình nhập API key** và mọi chỗ lưu/gửi `X-API-Key`. Client API: `fetch(..., { credentials: "same-origin" })`, đường dẫn **tương đối** (`/api/v1/...`). Biến `VITE_API_BASE_URL` (nếu có) mặc định rỗng ở bản build production; dev vẫn dùng proxy Vite sang `127.0.0.1:8000`.
- `AuthProvider` giữ `user` và `capabilities` trong **bộ nhớ** (React state), nạp bằng `GET /auth/me` khi khởi động. **Không** lưu gì vào `localStorage`/`sessionStorage`/cookie JS.
- Trang `/login`: ô `username`, `password` (`type="password"`, `autocomplete="current-password"`), có `<label>`, nút bị vô hiệu khi đang gửi, hiển thị lỗi bằng `role="alert"`. Đăng nhập xong chuyển đến trang trước đó hoặc `/`.
- Trang `/change-password`: bắt buộc khi `must_change_password`; ô mật khẩu hiện tại, mới, nhập lại; hiển thị quy tắc mật khẩu (≥ 12 ký tự…); `autocomplete="new-password"`.
- Thanh điều hướng: tên người dùng + nhãn vai trò, nút Đăng xuất; mục "Người dùng" và "Nhật ký bảo mật" chỉ cho admin.
- `useCan(action)` ánh xạ theo ma trận 5.1: `device:create`, `device:delete`, `audit:run`, `user:manage`, `events:read`. Nút không đủ quyền: **ẩn** (hành động phá hủy) hoặc **vô hiệu kèm tooltip** "Bạn không có quyền thực hiện thao tác này" (hành động thường). Vẫn xử lý `403` từ server bằng thông báo thân thiện.
- `RunAuditDialog`: nếu `capabilities.body_credentials=false` → không hiện ô username/password/enable secret, chỉ hiện nội dung "Server sẽ dùng thông tin đăng nhập SSH đã cấu hình sẵn" và gửi body `{}`.
- `UsersPage`: bảng người dùng (tên, vai trò, trạng thái, lần đăng nhập cuối); dialog tạo, đổi vai trò/khóa, đặt lại mật khẩu. Mật khẩu tạm do admin đặt chỉ hiển thị trong ô nhập, **không** hiển thị lại sau khi gửi.
- `SecurityEventsPage`: bảng sự kiện, lọc theo loại, nút "Tải thêm" (phân trang `before_id`).
- Mọi component mới dùng `Modal` hiện có (đã khóa focus); chữ hiển thị đưa vào `strings.ts`.
- Cập nhật `docs/frontend.md` (phần đăng nhập, bỏ phần API key).

---

## 11. Thứ tự thực hiện (dừng và chạy test sau mỗi bước)

1. **Chuẩn bị**: tạo branch `feat/auth-rbac`; liệt kê file hiện có (`wc -c`); đọc code theo quy tắc 9; ghi `pip freeze | grep -iE "paramiko|netmiko"` làm mốc; thêm `argon2-cffi` (ghim phiên bản) và kiểm tra hai gói mốc không đổi.
2. **Domain + security**: lỗi mới, entity, interface, `PasswordHasher`, `password_policy`, `tokens`, `client_ip`, `rate_limiter` + test 9.1, 9.5.
3. **Lưu trữ**: schema v2, ba repository SQLite + test 9.2.
4. **Services**: `AuthService`, `UserService`, `SecurityEventService` + test 9.3, 9.4.
5. **Config + middleware**: biến môi trường, kiểm tra khởi động chế độ công khai, middleware (Origin, Host, header) + test 9.8, 9.9 (phần khởi động).
6. **API**: `deps` (`resolve_principal`, `require_role`), routes `auth`, `users`, `security_events`; gắn `require_role` và ghi sự kiện vào route `devices`/`audits` hiện có; ghi đè validation handler cho endpoint mới + test 9.6, 9.7, 9.10 và phần còn lại của 9.9. **Các test API cũ phải xanh** (nhờ principal `api_key` ở chế độ dev).
7. **Phục vụ frontend + CLI**: `static.py`, `create_admin.py`, `reset_password.py` + test 9.11.
8. **Frontend nền**: client dùng cookie, `AuthProvider`, `RequireAuth`, `LoginPage`, `ChangePasswordPage`, bỏ API key + test 9.12 (phần đăng nhập).
9. **Frontend quyền & quản trị**: `useCan`/`RequireRole`, ẩn/vô hiệu nút, `RunAuditDialog` theo `capabilities`, `UsersPage`, `SecurityEventsPage` + test 9.12 (phần còn lại), 9.13.
10. **Tài liệu + kiểm chứng**: viết `docs/auth_and_deploy.md` (mục 12), chạy toàn bộ `pytest -q`, `npm run lint`, `typecheck`, `test`, `build`; thử tay theo mục 14.

---

## 12. Tài liệu vận hành `docs/auth_and_deploy.md` (nội dung bắt buộc)

### 12.1 Chạy demo qua Cloudflare Quick Tunnel (Giai đoạn 1)

```bash
# Trong venv đặc biệt (KHÔNG nâng/hạ paramiko/netmiko)
source .venv/bin/activate

# 1) Build frontend, backend sẽ phục vụ chung origin
(cd frontend && npm ci && npm run build)

# 2) Tạo admin lần đầu (hỏi mật khẩu bằng getpass)
python backend/scripts/create_admin.py --username admin

# 3) Biến môi trường chế độ công khai
export NETSENTRY_PUBLIC_MODE=1
export NETSENTRY_SERVE_FRONTEND=1
export NETSENTRY_ALLOWED_NETWORKS="192.168.1.0/24"     # dải thiết bị lab
export NETSENTRY_SSH_USERNAME="netsentry_lab"          # tài khoản SSH RIÊNG cho lab
export NETSENTRY_SSH_PASSWORD="..."                    # đặt trong shell, không ghi vào file repo
export NETSENTRY_ENABLE_SECRET="..."
export NETSENTRY_TRUSTED_IP_HEADER="CF-Connecting-IP"

# 4) Chạy backend, CHỈ bind loopback
cd backend && uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

# 5) Ở terminal khác, mở tunnel
cloudflared tunnel --url http://127.0.0.1:8000
# → in ra URL dạng https://<ngau-nhien>.trycloudflare.com
```

Ghi rõ **giới hạn của Quick Tunnel**: URL ngẫu nhiên và đổi mỗi lần chạy lại; không có SLA; giới hạn số request đồng thời; không hỗ trợ Server-Sent Events; **không** dùng được Cloudflare Access/WAF để giới hạn IP người truy cập; Cloudflare kết thúc TLS nên **nhìn thấy lưu lượng web dạng rõ** (kể cả mật khẩu đăng nhập NetSentry). Vì vậy: credentials SSH **không** đi qua web (chế độ công khai ép dùng biến môi trường phía server), và tài khoản demo là tài khoản dùng một lần.

**Checklist TRƯỚC demo**
- [ ] Tài khoản SSH riêng cho lab, quyền tối thiểu (chỉ đọc cấu hình), không dùng chung với tài khoản thật.
- [ ] `NETSENTRY_ALLOWED_NETWORKS` đúng dải lab.
- [ ] Admin dùng mật khẩu mạnh, **không** dùng lại mật khẩu ở nơi khác; tạo thêm 1 `operator` và 1 `viewer` để demo phân quyền.
- [ ] `/docs` trả 404 (kiểm tra bằng `curl`).
- [ ] Đăng nhập thử bằng cả 3 vai trò, kiểm tra ma trận quyền.
- [ ] Thiết bị demo là thiết bị lab, không phải thiết bị production.

**Checklist SAU demo**
- [ ] Tắt `cloudflared` (Ctrl+C) và dừng backend.
- [ ] **Đổi mật khẩu hoặc xóa** tài khoản SSH lab; đổi enable secret nếu đã dùng.
- [ ] Vô hiệu hóa hoặc đặt lại mật khẩu các tài khoản demo trong NetSentry.
- [ ] Xem `security_events` để phát hiện đăng nhập lạ (đặc biệt `LOGIN_FAILED`, `ACCESS_DENIED`).
- [ ] Xóa/đưa ra khỏi repo mọi file `data/raw_configs/*` nếu có.

### 12.2 Chạy dài hạn với domain riêng (Giai đoạn 2, hướng dẫn, chưa tự động hóa)

- Mua domain, thêm vào Cloudflare, tạo **Named Tunnel** (`cloudflared tunnel create`, `route dns`, file cấu hình `ingress` trỏ về `http://127.0.0.1:8000`), cài thành dịch vụ (`cloudflared service install`) để tự khởi động.
- Thêm domain vào `NETSENTRY_ALLOWED_HOSTS` (không cần sửa code).
- Bật **Cloudflare Access** (đăng nhập email/Google trước khi tới app; có thể giới hạn theo email/quốc gia/IP) như **lớp ngoài** bổ sung; đăng nhập NetSentry vẫn giữ nguyên vì RBAC là lớp trong.
- Chạy backend bằng service quản lý tiến trình (systemd) với biến môi trường lấy từ file có quyền `0600` ngoài repo; sao lưu định kỳ file SQLite (nay chứa hash mật khẩu và nhật ký); xoay vòng log.
- Xem xét chuyển rate-limit sang kho dùng chung nếu chạy nhiều tiến trình (ngoài phạm vi hiện tại).

### 12.3 Cảnh báo bảo mật cần có trong tài liệu

- Cookie phiên + CSRF: giải thích `SameSite=Strict` + kiểm tra `Origin`.
- Không bao giờ bật `NETSENTRY_AUTH_DISABLED=1` hoặc `NETSENTRY_API_KEY_AUTH=1` khi mở ra Internet.
- Quên mật khẩu admin: dùng `scripts/reset_password.py` trên máy chủ (không có reset qua email).

---

## 13. Để giai đoạn sau (KHÔNG làm ở đây)

- MFA (TOTP), SSO/OAuth, đọc danh tính từ Cloudflare Access (`resolve_principal` đã chừa chỗ).
- Quyền theo thiết bị, nhóm thiết bị.
- Rate-limit dùng Redis, khóa theo cặp (IP, username), CAPTCHA.
- Dashboard phiên đang hoạt động, "đăng xuất khỏi mọi thiết bị" do người dùng tự bấm.
- Mã hóa DB tại chỗ, ký/băm chuỗi `security_events` chống sửa.
- Docker, systemd unit tự động sinh.

---

## 14. Tiêu chí hoàn thành

- [ ] `pytest -q` (backend) xanh, gồm toàn bộ test cũ và test mới; `npm run lint`, `typecheck`, `test`, `build` xanh.
- [ ] `pip freeze` cho thấy `paramiko`, `netmiko` **không đổi** so với mốc.
- [ ] Test duyệt toàn bộ route khẳng định không route nào truy cập được khi chưa đăng nhập (ngoài whitelist).
- [ ] Ma trận quyền 3 vai trò × mọi endpoint đúng theo mục 5.1.
- [ ] Không tìm thấy mật khẩu, token thô, hash, SSH credentials trong: response, log, `security_events`, `localStorage`/`sessionStorage`, snapshot test.
- [ ] Khởi động `NETSENTRY_PUBLIC_MODE=1` bị từ chối khi vi phạm các điều kiện mục 7.
- [ ] **Thử tay** (ghi lại kết quả trong báo cáo cuối):
  1. Chạy `create_admin.py`, đăng nhập, bị ép đổi mật khẩu, đổi xong vào được dashboard.
  2. Tạo `operator` và `viewer`; đăng nhập từng người, kiểm tra nút hiển thị/ẩn và thử gọi API trái quyền bằng `curl` (nhận 403).
  3. Nhập sai mật khẩu 5 lần → bị khóa; đúng thông báo chung ở các lần sai.
  4. Mở bằng trình duyệt qua `cloudflared tunnel --url ...`: đăng nhập được, cookie có `Secure`/`HttpOnly`/`SameSite=Strict`, `/docs` trả 404, `security_events` ghi đúng `CF-Connecting-IP`.
  5. Chạy audit thật trên router lab bằng credentials từ biến môi trường, body `{}`; xác nhận body có `credentials` bị từ chối.
  6. Thêm thiết bị bằng `AddDeviceDialog`, **gõ liên tục nhiều ký tự mà focus không rời khỏi ô nhập**.
- [ ] Có `docs/auth_and_deploy.md` đủ mục 12 và báo cáo cuối liệt kê: file đã tạo/sửa, sai khác giữa đặc tả và code thật, các quyết định tự đưa ra, việc còn tồn đọng.
