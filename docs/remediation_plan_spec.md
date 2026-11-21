# NetSentry – Đặc tả Kế hoạch sửa lỗi: Đề xuất, Xem trước và Phê duyệt (Remediation C) cho Antigravity

> Cách dùng: lưu vào `docs/remediation_plan_spec.md`, mở Antigravity ở chế độ **Planning**, gửi: *"Đọc @docs/remediation_plan_spec.md và thực hiện đúng từng bước ở mục 12. Đưa plan trước, đợi tôi duyệt rồi mới code. Sau mỗi bước dừng lại và dán output thô."*
> Quy ước ngôn ngữ: giải thích bằng tiếng Việt; tên file/class/hàm/biến, docstring, comment, thông báo lỗi và mô tả API viết bằng tiếng Anh; **chữ hiển thị trên giao diện viết bằng tiếng Việt** (gom vào `frontend/src/i18n/strings.ts`). Ngoại lệ có chủ đích: các đoạn mô tả **tác động/rủi ro** trong mẫu sửa lỗi (mục 4.3) là dữ liệu hiển thị cho người dùng cuối nên viết bằng tiếng Việt ngay trong mã nguồn mẫu.
> **Điều kiện đầu vào:** module Auth + RBAC đã xong, đã merge, `bash scripts/verify_all.sh` xanh. Module Snapshot + AI và Baseline **không bắt buộc** cho giai đoạn này, nhưng cần xong trước khi làm bước thực thi (Remediation D). Tạo branch mới `feat/remediation-plan`.

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư full-stack senior, chuyên bảo mật ứng dụng. Hãy thêm vào NetSentry luồng **Đề xuất sửa → Xem trước → Phê duyệt** cho một số lỗi cấu hình đã phát hiện. **Giai đoạn này TUYỆT ĐỐI không gửi bất kỳ lệnh nào xuống thiết bị**: không dùng `ConnectorFactory`, không mở SSH. Việc thực thi là giai đoạn sau (Remediation D) và có đặc tả riêng.

Nguyên tắc thiết kế xuyên suốt: **lệnh sửa chỉ đến từ mẫu cố định đã được con người kiểm chứng trong mã nguồn**. Không đến từ AI, không đến từ nội dung cấu hình hay `evidence` của finding, không đến từ người dùng nhập. Mục đích: một dòng `description`/banner độc hại trong cấu hình thiết bị (prompt injection hoặc chèn lệnh) không bao giờ biến thành lệnh chạy trên thiết bị.

Quy tắc bắt buộc:

1. Làm đúng thứ tự mục 12. Sau mỗi bước chạy `pytest -q backend/` **từ thư mục gốc repo** (đã `source .venv/bin/activate`) và, với bước frontend, `npm run lint`, `npm run typecheck`, `npm test`. Chỉ đi tiếp khi xanh. **Toàn bộ test hiện có phải tiếp tục xanh.**
2. Không thêm tính năng ngoài phạm vi (mục 1). Đặc tả mơ hồ hoặc mâu thuẫn → **dừng lại và hỏi**.
3. **Mỗi file `.py` vừa tạo/sửa phải chạy ngay `python -m py_compile <file>`** (từ `backend/`) trước khi chạy cả bộ test. **Ghi đè toàn bộ nội dung file**, không ghi nối (append).
4. Mỗi hành vi mới có test viết **trước**, chạy thấy thất bại, rồi mới sửa cho xanh. Tổng số test phải **tăng**.
5. Báo cáo mỗi bước chỉ gồm: danh sách file tạo/sửa, **output thô nguyên văn** của lệnh test, tổng số test trước/sau, việc chưa làm. **Không** dùng cụm "hoàn thành" khi còn lệnh chưa chạy hoặc chưa xanh. Cuối cùng đính kèm output của `bash scripts/verify_all.sh`.
6. Test không mở kết nối mạng thật. Có một test kiến trúc **chứng minh giai đoạn này không chạm thiết bị** (mục 9.10).
7. **Không đụng vào phiên bản `netmiko` và `paramiko`; không thêm thư viện mới.** Ghi `pip freeze` trước/sau và `diff`.
8. Sửa file hiện có chỉ ở các điểm mục 3 đánh dấu "SỬA". Không sửa Rule Engine, parser, rule, Connector, `AuditService`. **Đọc code thật** của `AuditRunService`, entity `Finding`/`AuditRun`, `AuthService` trước khi sửa hoặc tái sử dụng; code thật là chuẩn, sai khác với spec thì ghi vào báo cáo.
9. Không bao giờ log, trả về, hay lưu vào `security_events`/`remediation_events`: mật khẩu (kể cả mật khẩu xác nhận khi duyệt), credentials, session token, raw config.
10. Python 3.11+, type hints đầy đủ; route handler viết bằng `def`. Frontend TypeScript `strict`, không `any`, không `eslint-disable` trừ khi ghi lý do cụ thể.

---

## 1. Phạm vi

**Làm**

- **Mẫu sửa lỗi** (`RemediationTemplate`) cố định, có phiên bản, cho đúng 2 rule: `NET-008` và `NET-004`. Các rule còn lại chỉ có **hướng dẫn thủ công** (không tạo kế hoạch thực thi).
- **Kế hoạch sửa** (`RemediationPlan`) tạo từ một finding `FAIL`, kèm **xem trước** (lệnh chính xác, tác động, rủi ro, kỳ vọng xác minh).
- **Kiểm tra hợp lệ** phía server (rule đủ điều kiện, finding còn `FAIL`, audit không cũ, không trùng kế hoạch đang hoạt động).
- **Vòng đời** `PROPOSED → APPROVED | REJECTED | CANCELLED | EXPIRED` với chuyển trạng thái nguyên tử.
- **Phê duyệt có kiểm soát**: chỉ admin, **khác người đề xuất**, **nhập lại mật khẩu** (step-up), gắn với **mã băm kế hoạch** (`plan_hash`), tự hết hạn.
- Nhật ký từng kế hoạch (`remediation_events`, chỉ thêm) và sự kiện bảo mật tóm tắt.
- API (mục 7), RBAC, biến môi trường (mục 6).
- Frontend: nút "Đề xuất sửa" ở finding đủ điều kiện, hộp thoại xem trước, trang danh sách/chi tiết kế hoạch, hộp thoại duyệt/từ chối/hủy.
- Tài liệu `docs/remediation_workflow.md`.

**KHÔNG làm** (để Remediation D hoặc sau đó)

- **Thực thi lệnh lên thiết bị**, xác minh sau khi sửa, hoàn tác, `write memory`. Các trạng thái dành cho D được **đặt chỗ** trong schema nhưng **không có đường nào đi tới** ở giai đoạn này.
- Bất kỳ đường nào cho AI sinh, chọn hoặc sửa lệnh. (AI chỉ giải thích/sắp xếp ưu tiên ở module Snapshot + AI; module đó không được import vào gói remediation.)
- Mẫu sửa cho các rule `NET-001/002/003/005/006/007` (rủi ro tự khóa mình khỏi router hoặc cần chọn mật khẩu/ACL).
- Mẫu có tham số do người dùng nhập, kế hoạch gồm nhiều lệnh từ nhiều rule, duyệt hàng loạt.
- Thông báo email/Slack, lên lịch thực thi.

---

## 2. Ràng buộc kiến trúc

- Gói `app/remediation/` (mẫu, chính sách lệnh, băm kế hoạch, máy trạng thái) là **logic thuần**: chỉ thư viện chuẩn và `app.domain`. **Cấm import**: `app.connectors`, `app.factories`, `app.clients`, các service AI (`ai_*`), `netmiko`, `paramiko`, `urllib`, `socket`, `subprocess`. Có test kiến trúc bằng `ast` (mục 9.10).
- `RemediationService` (trong `app/services/`) **không** nhận `ConnectorFactory` hay bất kỳ đối tượng kết nối thiết bị nào qua constructor.
- `sqlite3` chỉ trong `app/repositories/`. `fastapi`/`pydantic`/`starlette` chỉ trong `app/api/` và `main.py`. `api` chỉ gọi `services`.
- Route handler viết bằng `def`. Cập nhật `tests/unit/test_architecture_imports.py`.

---

## 3. Cây thư mục (chỉ file thuộc giai đoạn này)

```
backend/
  app/
    domain/
      errors.py                       # SỬA: chỉ THÊM lỗi mới (mục 4.1)
      entities/
        remediation.py                # RemediationPlan, PlanStatus, RiskLevel, PlanEvent
        security_event.py             # SỬA: THÊM loại sự kiện (mục 4.5)
      interfaces/
        remediation_repository.py
    remediation/
      __init__.py
      templates.py                    # RemediationTemplate + registry (NET-008, NET-004)
      command_policy.py               # allowlist lệnh cấu hình + kiểm tra
      plan_hash.py                    # băm chuẩn hóa kế hoạch
      state_machine.py                # bảng chuyển trạng thái hợp lệ
    repositories/
      database.py                     # SỬA: thêm bảng (mục 5), tăng user_version lên giá trị kế tiếp
      sqlite_remediation_repository.py
    services/
      remediation_service.py
      auth_service.py                 # SỬA: THÊM verify_password_for_user (mục 8.4)
    api/
      routes/remediation.py
      schemas/remediation.py
    core/config.py                    # SỬA: biến môi trường mục 6
    main.py                           # SỬA: dựng service, router
  tests/                              # theo mục 9
frontend/
  src/
    components/remediation/RemediationPreviewDialog.tsx, ApproveDialog.tsx, RejectDialog.tsx,
                           PlanStatusBadge.tsx, PlanTimeline.tsx, ManualGuidance.tsx
    pages/RemediationPlansPage.tsx, RemediationPlanDetailPage.tsx
    pages/                            # SỬA: AuditRunPage (nút ở finding), App.tsx (route), AppShell (menu)
    i18n/strings.ts                   # SỬA
    types/api.ts                      # SỬA
docs/
  remediation_workflow.md
```

---

## 4. Đặc tả domain

### 4.1 Lỗi mới (`domain/errors.py`, chỉ thêm)

```python
class RemediationDisabledError(NetSentryError):   code = "REMEDIATION_DISABLED"          # 503
class NotEligibleError(NetSentryError):           code = "REMEDIATION_NOT_ELIGIBLE"      # 422 (rule không có mẫu / platform sai)
class FindingNotFailingError(NetSentryError):     code = "FINDING_NOT_FAILING"           # 422
class ActivePlanExistsError(NetSentryError):      code = "ACTIVE_PLAN_EXISTS"            # 409
class PlanNotFoundError(NetSentryError):          code = "PLAN_NOT_FOUND"                # 404
class PlanStaleError(NetSentryError):             code = "PLAN_STALE"                    # 409
class PlanExpiredError(NetSentryError):           code = "PLAN_EXPIRED"                  # 409
class InvalidTransitionError(NetSentryError):     code = "INVALID_TRANSITION"            # 409
class SelfApprovalError(NetSentryError):          code = "SELF_APPROVAL_NOT_ALLOWED"     # 403
class ReauthFailedError(NetSentryError):          code = "REAUTH_FAILED"                 # 422
class UserSessionRequiredError(NetSentryError):   code = "USER_SESSION_REQUIRED"         # 403 (API key / auth tắt không được đề xuất/duyệt)
```

Cập nhật `api/errors.py` ánh xạ mã HTTP ở trên.

### 4.2 Entity

```python
class RiskLevel(str, Enum):   LOW = "LOW"; MEDIUM = "MEDIUM"; HIGH = "HIGH"

class PlanStatus(str, Enum):
    # dùng ở giai đoạn này
    PROPOSED = "PROPOSED"; APPROVED = "APPROVED"; REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"; EXPIRED = "EXPIRED"
    # ĐẶT CHỖ cho Remediation D, chưa có đường chuyển tới ở giai đoạn này
    APPLYING = "APPLYING"; APPLIED = "APPLIED"; VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"; FAILED = "FAILED"; ROLLED_BACK = "ROLLED_BACK"

@dataclass(frozen=True)
class RemediationPlan:
    id: int
    device_id: str
    run_id: int                       # audit nguồn
    rule_id: str
    template_id: str
    template_version: int
    risk_level: RiskLevel
    commands: tuple[str, ...]         # đúng các dòng sẽ được gửi (ở giai đoạn D)
    persist_after_verify: bool        # có `write memory` sau khi xác minh (D); mặc định False
    plan_hash: str
    status: PlanStatus
    proposed_by: str; proposed_at: datetime
    decided_by: str | None; decided_at: datetime | None; decision_reason: str | None
    approved_plan_hash: str | None
    expires_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class PlanEvent:
    id: int; plan_id: int; occurred_at: datetime
    actor: str | None; event_type: str; detail: str | None
```

### 4.3 Mẫu sửa lỗi (`remediation/templates.py`)

```python
@dataclass(frozen=True)
class RemediationTemplate:
    template_id: str; version: int; rule_id: str
    platforms: tuple[str, ...]
    risk_level: RiskLevel
    commands: tuple[str, ...]            # HẰNG SỐ, không có tham số, không nội suy chuỗi
    impact_vi: str                        # mô tả tác động (tiếng Việt)
    risks_vi: tuple[str, ...]             # các rủi ro/lưu ý
    expected_verification: tuple[str, str]  # ("NET-008", "PASS")
    reversible: bool
    rollback_note_vi: str
```

Hai mẫu duy nhất ở giai đoạn này (nội dung tiếng Việt do bạn soạn cho sát thực tế; ý chính bắt buộc):

- **`NET-008-v1`**: `commands = ("no ip http server",)`, `risk_level=LOW`. Tác động: tắt máy chủ HTTP không mã hóa (cổng 80). Rủi ro: nếu đang quản lý thiết bị qua giao diện web HTTP sẽ mất truy cập web (không ảnh hưởng SSH); `ip http secure-server` (HTTPS) không bị đụng tới. `reversible=True` (`ip http server`).
- **`NET-004-v1`**: `commands = ("service password-encryption",)`, `risk_level=LOW`. Tác động: mã hóa dạng type 7 các mật khẩu văn bản đang có trong cấu hình. Rủi ro/lưu ý: type 7 là mã hóa yếu, **chỉ chống nhìn trộm**, không thay thế `enable secret`; **tắt lại bằng `no service password-encryption` không giải mã** các mật khẩu đã bị mã hóa. `reversible=False` về mặt thực chất; ghi rõ trong `rollback_note_vi`.

Quy tắc bất biến (có test, mục 9.1):

- `commands` là tuple hằng, **mỗi phần tử một dòng**, không chứa `\n`, `\r`, `;`, `|`, backtick, và độ dài ≤ 120 ký tự.
- `commands` phải **khớp chính xác** một mục của `COMMAND_ALLOWLIST` (mục 4.4).
- Kế hoạch **không bao giờ nội suy** dữ liệu từ finding, evidence, cấu hình hay người dùng vào `commands`. Hàm `build_plan_draft(template, finding)` chỉ đọc `rule_id`/`device_id`/`run_id` để gắn nhãn, không đưa vào lệnh.
- Registry tra theo `rule_id`; rule không có mẫu → `NotEligibleError`. Mỗi mẫu có `version`; đổi lệnh hoặc nội dung phải tăng `version`.

### 4.4 Chính sách lệnh (`remediation/command_policy.py`)

```python
COMMAND_ALLOWLIST: frozenset[str] = frozenset({
    "no ip http server",
    "service password-encryption",
})
FORBIDDEN_TOKENS = ("reload", "erase", "delete", "format", "copy", "write", "configure",
                    "conf t", "username", "enable", "crypto key", "tftp", "ftp", "scp",
                    "boot", "shutdown", "transport", "access-class", "line ")
```

`validate_commands(commands)`: từng dòng phải **bằng chính xác** một phần tử của `COMMAND_ALLOWLIST` (so sánh nguyên chuỗi, phân biệt chữ hoa/thường, không `strip` mơ hồ), đồng thời không chứa token cấm và không trống. Sai → `ValueError` (lỗi lập trình, không phải lỗi người dùng). Hàm này sẽ được **gọi lại ở Remediation D ngay trước khi gửi lệnh**. Thêm lệnh mới vào allowlist luôn đi kèm mẫu mới và test.

### 4.5 Sự kiện bảo mật mới (thêm vào `SecurityEventType`)

`REMEDIATION_PROPOSED`, `REMEDIATION_APPROVED`, `REMEDIATION_REJECTED`, `REMEDIATION_CANCELLED`. **Frontend `SecurityEventsPage` phải cập nhật `EVENT_TYPES` cho khớp**; đã có test đối chiếu frontend/backend từ các module trước, nó phải xanh.

### 4.6 Băm kế hoạch (`remediation/plan_hash.py`)

`compute_plan_hash(device_id, rule_id, template_id, template_version, commands, persist_after_verify) -> str`: SHA-256 hex của JSON chuẩn hóa (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`). Đổi bất kỳ trường nào làm hash đổi. Giá trị này được lưu ở `plan_hash` khi đề xuất và chép sang `approved_plan_hash` khi duyệt; Remediation D **tính lại và so khớp** trước khi chạy (chống sửa đổi sau duyệt).

### 4.7 Máy trạng thái (`remediation/state_machine.py`)

Chỉ các chuyển sau hợp lệ ở giai đoạn này:

```
PROPOSED → APPROVED | REJECTED | CANCELLED | EXPIRED
APPROVED → CANCELLED | EXPIRED
```

`REJECTED`, `CANCELLED`, `EXPIRED` là **trạng thái cuối** (không đổi nữa). Các trạng thái dành cho D không có chuyển nào đi tới. Mọi chuyển khác → `InvalidTransitionError`. Chuyển trạng thái ở tầng lưu trữ phải **nguyên tử**: `UPDATE ... SET status=? WHERE id=? AND status=?` và kiểm tra `rowcount == 1`, để hai người duyệt cùng lúc không thể cùng thành công (mục 9.4).

---

## 5. Lưu trữ

`init_db` idempotent. Tăng `PRAGMA user_version` lên **giá trị kế tiếp** sau phiên bản hiện tại (đọc `database.py`; thường là 5 nếu các module Snapshot và Baseline đã xong, nếu chưa thì giá trị kế tiếp tương ứng) bằng `CREATE TABLE IF NOT EXISTS` (không đụng bảng cũ).

```sql
CREATE TABLE IF NOT EXISTS remediation_plans (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id            TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  run_id               INTEGER NOT NULL,                  -- KHÔNG đặt khóa ngoại: giữ vết kể cả khi audit nguồn bị dọn
  rule_id              TEXT NOT NULL,
  template_id          TEXT NOT NULL,
  template_version     INTEGER NOT NULL,
  risk_level           TEXT NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
  commands_json        TEXT NOT NULL,
  persist_after_verify INTEGER NOT NULL DEFAULT 0,
  plan_hash            TEXT NOT NULL,
  status               TEXT NOT NULL CHECK (status IN (
      'PROPOSED','APPROVED','REJECTED','CANCELLED','EXPIRED',
      'APPLYING','APPLIED','VERIFIED','VERIFY_FAILED','FAILED','ROLLED_BACK')),
  proposed_by          TEXT NOT NULL,
  proposed_at          TEXT NOT NULL,
  decided_by           TEXT,
  decided_at           TEXT,
  decision_reason      TEXT,
  approved_plan_hash   TEXT,
  expires_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL
);
-- mỗi (thiết bị, rule) chỉ có tối đa một kế hoạch đang hoạt động
CREATE UNIQUE INDEX IF NOT EXISTS idx_plan_active
  ON remediation_plans(device_id, rule_id)
  WHERE status IN ('PROPOSED','APPROVED','APPLYING');
CREATE INDEX IF NOT EXISTS idx_plan_device ON remediation_plans(device_id, proposed_at DESC);

CREATE TABLE IF NOT EXISTS remediation_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id     INTEGER NOT NULL REFERENCES remediation_plans(id) ON DELETE CASCADE,
  occurred_at TEXT NOT NULL,
  actor       TEXT,
  event_type  TEXT NOT NULL,
  detail      TEXT                                   -- ≤ 200 ký tự, không chứa bí mật
);
CREATE INDEX IF NOT EXISTS idx_plan_events ON remediation_events(plan_id, id);
```

Lý do danh sách trạng thái đầy đủ ngay từ đầu: `CHECK` trong SQLite rất khó đổi về sau (phải dựng lại bảng), nên các trạng thái của giai đoạn D được đặt chỗ sẵn. `remediation_events` là **chỉ thêm** (repository không có hàm sửa/xóa lẻ; chỉ bị xóa dây chuyền khi xóa thiết bị). (Tên bảng/cột khóa ngoại phải khớp schema thật.)

---

## 6. Cấu hình (`core/config.py`)

| Biến | Mặc định | Mô tả |
|---|---|---|
| `NETSENTRY_REMEDIATION_ENABLED` | `0` | Bật tính năng kế hoạch sửa. Tắt: `POST` trả `503 REMEDIATION_DISABLED`, `GET` trả danh sách rỗng, giao diện ẩn mục. |
| `NETSENTRY_REMEDIATION_PROPOSAL_TTL_MINUTES` | `120` | Hạn của kế hoạch `PROPOSED` (5–1440). |
| `NETSENTRY_REMEDIATION_APPROVAL_TTL_MINUTES` | `60` | Hạn hiệu lực sau khi `APPROVED` (5–1440); quá hạn thì `EXPIRED`. |
| `NETSENTRY_REMEDIATION_MAX_AUDIT_AGE_MINUTES` | `60` | Audit nguồn không được cũ hơn mức này (khi đề xuất **và** khi duyệt). |
| `NETSENTRY_REMEDIATION_REQUIRE_DISTINCT_APPROVER` | `1` | Người duyệt phải khác người đề xuất. **Bị ép về 1** khi `PUBLIC_MODE=1`. Đặt `0` chỉ để thử một mình trong lab; ghi cảnh báo vào log khi khởi động. |

Chế độ công khai (`NETSENTRY_PUBLIC_MODE=1`): giai đoạn này không ghi gì xuống thiết bị nên đề xuất/duyệt vẫn dùng được, nhưng `REQUIRE_DISTINCT_APPROVER` bị ép về `1`. (Việc thực thi ở Remediation D sẽ bị tắt hẳn ở chế độ công khai.)

---

## 7. API (`/api/v1`) và phân quyền

| Phương thức | Đường dẫn | Quyền | Mô tả | Thành công | Lỗi |
|---|---|---|---|---|---|
| `GET` | `/remediation/templates` | viewer+ | Danh sách mẫu (rule, rủi ro, tác động, đủ điều kiện) và danh sách rule **chỉ có hướng dẫn thủ công** | `200` | `401`, `403` |
| `POST` | `/audits/{run_id}/findings/{rule_id}/remediation` | **operator+** | Tạo kế hoạch `PROPOSED`. Body: `{persist_after_verify?: bool}` (mặc định `false`) | `201` | `401`, `403 USER_SESSION_REQUIRED`, `404`, `409 ACTIVE_PLAN_EXISTS/PLAN_STALE`, `422 REMEDIATION_NOT_ELIGIBLE/FINDING_NOT_FAILING`, `503` |
| `GET` | `/devices/{id}/remediation-plans?status=&limit=` | viewer+ | Danh sách kế hoạch (mới nhất trước, `limit` mặc định 30, tối đa 200) | `200` | `401`, `403`, `404`, `422` |
| `GET` | `/remediation-plans/{plan_id}` | viewer+ | Chi tiết + xem trước + dòng thời gian | `200` | `401`, `403`, `404 PLAN_NOT_FOUND` |
| `POST` | `/remediation-plans/{plan_id}/approve` | **admin** | Body `{password}` (nhập lại mật khẩu) | `200` | `401`, `403 SELF_APPROVAL_NOT_ALLOWED/USER_SESSION_REQUIRED`, `404`, `409 INVALID_TRANSITION/PLAN_EXPIRED/PLAN_STALE`, `422 REAUTH_FAILED`, `429` |
| `POST` | `/remediation-plans/{plan_id}/reject` | **admin** | Body `{reason}` (bắt buộc, ≤ 200 ký tự) | `200` | `401`, `403`, `404`, `409`, `422` |
| `POST` | `/remediation-plans/{plan_id}/cancel` | operator+ (chính người đề xuất) hoặc admin | Hủy khi `PROPOSED`/`APPROVED` | `200` | `401`, `403`, `404`, `409` |

Phản hồi chi tiết (`GET /remediation-plans/{id}`) gồm: `id`, `device_id`, `rule_id`, `status`, `risk_level`, **`commands`** (đúng các dòng), `persist_after_verify`, `impact`, `risks`, `expected_verification` (`{rule_id, expected_status: "PASS"}`), `reversible`, `rollback_note`, `proposed_by/at`, `decided_by/at/reason`, `expires_at`, `plan_hash`, `timeline` (các `PlanEvent`). **Không** trả `approved_plan_hash` ra ngoài mức cần thiết (chỉ trả cờ `approved_hash_matches: bool`).

Quy tắc chung:

- Mọi route phải có `require_role(...)`; test duyệt toàn bộ `app.routes` hiện có phải tiếp tục xanh.
- Chỉ **principal phiên người dùng thật** mới được đề xuất/duyệt/từ chối/hủy. Principal `api_key` hoặc `disabled` (dev) → `403 USER_SESSION_REQUIRED` (cần danh tính cá nhân để quy trách nhiệm và có mật khẩu để xác nhận).
- `cancel`: operator chỉ hủy được kế hoạch **do chính mình đề xuất**; admin hủy được mọi kế hoạch.
- Hết hạn được áp dụng **lười biếng** (khi đọc/ghi một kế hoạch quá hạn thì chuyển `EXPIRED` và ghi sự kiện) và **khi khởi động** (quét một lượt). Không dùng tác vụ nền.
- Lỗi giữ dạng `{"error": {"code", "message"}}`; trường `reason`, `password` không bao giờ lọt vào log hay thông báo lỗi.

---

## 8. Đặc tả dịch vụ

### 8.1 Tạo kế hoạch (`RemediationService.propose`)

Các bước (theo thứ tự, dừng ở lỗi đầu tiên):

1. `REMEDIATION_ENABLED`, principal là phiên người dùng.
2. Lấy audit run `run_id`: phải tồn tại và `COMPLETED`; finding của `rule_id` trong run đó phải tồn tại. (Giả định mỗi `rule_id` có một finding mỗi run; đọc code thật, nếu khác thì ghi vào báo cáo.)
3. Mẫu: tra registry theo `rule_id` (không có → `NotEligibleError`); `device.platform` phải nằm trong `template.platforms`.
4. Finding phải có `status == FAIL` (nếu không → `FindingNotFailingError`).
5. **Không cũ**: `run_id` phải là audit `COMPLETED` **mới nhất** của thiết bị và tuổi ≤ `MAX_AUDIT_AGE_MINUTES`; nếu không → `PlanStaleError` (`message` bảo chạy audit lại).
6. Dựng `commands` từ mẫu, gọi `validate_commands`, tính `plan_hash`, lưu với `status=PROPOSED`, `expires_at = now + PROPOSAL_TTL`. Vi phạm chỉ mục một phần → `ActivePlanExistsError` (chuyển lỗi `IntegrityError` thành lỗi nghiệp vụ, không lộ chi tiết SQL).
7. Ghi `remediation_events` (`PROPOSED`) và tầng route ghi `REMEDIATION_PROPOSED`.

### 8.2 Duyệt, từ chối, hủy

`approve(plan_id, approver, password, client_ip)`:

1. `REMEDIATION_ENABLED`; approver là phiên người dùng **admin**.
2. Nạp kế hoạch; nếu quá hạn → chuyển `EXPIRED`, ghi sự kiện, ném `PlanExpiredError`. Phải đang `PROPOSED` (`InvalidTransitionError` nếu không).
3. **Khác người đề xuất** khi `REQUIRE_DISTINCT_APPROVER=1` (nếu không → `SelfApprovalError`, ghi `ACCESS_DENIED`).
4. **Kiểm tra lại độ mới**: audit nguồn vẫn là audit mới nhất, chưa quá `MAX_AUDIT_AGE_MINUTES`, và finding đó **vẫn là `FAIL`**. Nếu đã có audit mới hơn hoặc finding đã `PASS` → chuyển `EXPIRED` và ném `PlanStaleError`.
5. **Tính lại** `plan_hash` từ mẫu hiện hành và so với `plan_hash` đã lưu; lệch (ví dụ mẫu đã đổi phiên bản) → `PlanStaleError`.
6. **Xác nhận lại danh tính** (step-up): `AuthService.verify_password_for_user` (mục 8.4); sai → `ReauthFailedError`.
7. Chuyển `PROPOSED → APPROVED` bằng cập nhật nguyên tử, đặt `decided_by/decided_at`, `approved_plan_hash = plan_hash`, `expires_at = now + APPROVAL_TTL`. Ghi `remediation_events` và `REMEDIATION_APPROVED`.

`reject(plan_id, approver, reason)`: admin; chỉ từ `PROPOSED`; `reason` bắt buộc, làm sạch ký tự điều khiển, ≤ 200 ký tự; cho phép cả khi kế hoạch do chính admin đề xuất. `cancel(plan_id, actor)`: theo quy tắc mục 7. Mọi chuyển trạng thái đều qua `state_machine` và cập nhật nguyên tử; đối với lỗi `rowcount != 1` ném `InvalidTransitionError`.

### 8.3 Hướng dẫn thủ công (rule không có mẫu)

`GET /remediation/templates` trả thêm, cho mỗi rule còn lại (`NET-001/002/003/005/006/007`), phần **hướng dẫn thủ công** lấy từ `remediation`/`verification` đã có sẵn của rule (văn bản tĩnh), cùng lý do không tự động (vd "có thể làm mất truy cập quản trị"). Đây **không** tạo kế hoạch và không có nút duyệt.

### 8.4 Step-up trong `AuthService` (SỬA, chỉ thêm)

Thêm `verify_password_for_user(user_id, password, client_ip) -> None`: lấy hash của user, `verify`; sai thì tăng bộ đếm sai bằng **cùng cơ chế khóa tài khoản** như đăng nhập (`register_failed_attempt`, ghi `LOGIN_FAILED`/`LOGIN_LOCKED`, nếu khóa thì thu hồi phiên và ném `AccountLockedError`), rồi ném `ReauthFailedError`. Đúng thì không ghi gì thêm. **Không** tạo phiên mới và không đổi trạng thái người dùng. Tái sử dụng mã chung với `change_password` thay vì sao chép (refactor nhỏ, test hiện có của `change_password` phải xanh).

---

## 9. Yêu cầu test

Dùng DB tạm (`tmp_path`), `Clock` giả, `FakeConnector` chỉ để dựng audit. Test thất bại **trước** khi sửa (quy tắc 4).

1. **Mẫu và chính sách lệnh**: mọi mẫu trong registry có `commands` khớp chính xác `COMMAND_ALLOWLIST`; không dòng nào chứa `\n`, `\r`, `;`, `|`, backtick hoặc token cấm; rule không có mẫu (`NET-001`…) tra ra `NotEligibleError`; `validate_commands` từ chối: dòng ngoài allowlist, dòng có tiền tố/hậu tố lạ (`"no ip http server "`, `"NO IP HTTP SERVER"`, `"no ip http server\nreload"`), dòng trống, danh sách rỗng; mọi mẫu có `version` và nội dung tác động không rỗng.
2. **Chống chèn lệnh**: tạo kế hoạch từ finding có `evidence` chứa `"\nreload\n"`, `"; write erase"`, chuỗi giả chỉ dẫn LLM; `commands` của kế hoạch **vẫn chính xác bằng** lệnh của mẫu (bất biến). Thử thêm một đối tượng finding giả có `rule_id` lạ → `NotEligibleError`.
3. **`plan_hash`**: ổn định (cùng đầu vào, cùng kết quả), đổi khi đổi bất kỳ trường nào (`device_id`, `rule_id`, `template_version`, `commands`, `persist_after_verify`), không phụ thuộc thứ tự khóa.
4. **Máy trạng thái và lưu trữ (SQLite thật)**: các chuyển hợp lệ/không hợp lệ theo mục 4.7 (bao gồm mọi trạng thái cuối và trạng thái đặt chỗ của D không có đường tới); **hai lần `approve` đồng thời trên cùng kế hoạch chỉ một lần thành công** (dùng hai kết nối/luồng); chỉ mục một phần chặn kế hoạch đang hoạt động thứ hai cho cùng (thiết bị, rule) nhưng cho phép kế hoạch mới sau khi bản cũ `REJECTED/CANCELLED/EXPIRED`; cascade khi xóa thiết bị; truy vấn tham số hóa; `remediation_events` không có hàm sửa/xóa lẻ.
5. **`RemediationService.propose`**: thành công; audit không `COMPLETED`; rule không đủ điều kiện; finding không `FAIL` → `FindingNotFailingError`; audit không phải mới nhất hoặc quá cũ → `PlanStaleError`; trùng kế hoạch đang hoạt động → `ActivePlanExistsError`; `persist_after_verify` được lưu và nằm trong `plan_hash`; `REMEDIATION_ENABLED=0` → `RemediationDisabledError`.
6. **`approve` / `reject` / `cancel`**: thành công; **tự duyệt bị chặn** khi `REQUIRE_DISTINCT_APPROVER=1` (và ghi `ACCESS_DENIED`), cho phép khi `0`; **mật khẩu sai → `ReauthFailedError`, tăng bộ đếm, đủ số lần sai thì khóa tài khoản**; mật khẩu **không** xuất hiện trong response, log, `security_events`, `remediation_events`; quá hạn → `EXPIRED` + `PlanExpiredError` (dùng `Clock` giả); có audit mới hơn trước khi duyệt → `EXPIRED` + `PlanStaleError`; finding đã `PASS` ở audit mới → `PlanStaleError`; mẫu đổi `version` sau khi đề xuất → `PlanStaleError`; `reject` yêu cầu `reason`; `cancel`: operator hủy được kế hoạch của mình, **không** hủy được của người khác, admin hủy được tất cả; kế hoạch đã ở trạng thái cuối không đổi được.
7. **Phiên người dùng**: principal `api_key` và `disabled` bị `403 USER_SESSION_REQUIRED` ở `propose/approve/reject/cancel`.
8. **API và RBAC**: ma trận quyền mục 7 (mỗi vai trò × mỗi endpoint); test duyệt toàn bộ `app.routes` vẫn xanh; sự kiện `REMEDIATION_PROPOSED/APPROVED/REJECTED/CANCELLED` được ghi; `GET /remediation/templates` trả đúng 2 mẫu đủ điều kiện và đủ 6 rule thủ công; chi tiết kế hoạch không có `approved_plan_hash` thô; khởi động quét và chuyển `EXPIRED` các kế hoạch quá hạn.
9. **Cấu hình**: `REQUIRE_DISTINCT_APPROVER` bị ép về `1` ở chế độ công khai; các biến TTL sai khoảng giá trị → từ chối khởi động với thông báo rõ.
10. **Kiến trúc, chứng minh không chạm thiết bị**: `ast` kiểm tra gói `app/remediation/` và `remediation_service.py` **không** import `connectors`, `factories`, `clients`, `ai_*`, `netmiko`, `paramiko`, `urllib`, `socket`, `subprocess`; `RemediationService` khởi tạo **không cần** `ConnectorFactory`; test tích hợp: dùng `FakeConnector` có bộ đếm số lần `connect`, thực hiện toàn bộ chu trình đề xuất → duyệt và khẳng định bộ đếm **bằng 0** sau lúc dựng audit; `pip freeze` không đổi; **test đối chiếu `EVENT_TYPES` frontend/backend** vẫn xanh.
11. **Frontend (Vitest + MSW, qua `renderWithProviders`; không mock `AuthProvider`)**:
    - Nút "Đề xuất sửa" chỉ hiện ở finding `FAIL` của rule đủ điều kiện và **chỉ cho operator/admin**; viewer không thấy; rule thủ công hiện `ManualGuidance` và **không** có nút.
    - `RemediationPreviewDialog`: hiển thị **đúng từng dòng lệnh** trong khối mã (văn bản thuần), mức rủi ro, tác động, rủi ro, kỳ vọng xác minh, lựa chọn `persist_after_verify` (mặc định tắt, có giải thích); xử lý đủ lỗi `ACTIVE_PLAN_EXISTS`, `PLAN_STALE`, `FINDING_NOT_FAILING`, `REMEDIATION_DISABLED`.
    - `ApproveDialog`: chỉ admin thấy nút Duyệt; yêu cầu nhập mật khẩu và tích xác nhận "Tôi đã xem các lệnh"; hiển thị `REAUTH_FAILED`, `SELF_APPROVAL_NOT_ALLOWED`, `PLAN_EXPIRED`, `PLAN_STALE` bằng thông báo thân thiện; **mật khẩu không được lưu vào storage** và xóa khỏi state sau khi gửi.
    - `RejectDialog` bắt buộc lý do; `PlanTimeline` đúng thứ tự; văn bản do người dùng nhập (`reason`) hiển thị dạng thuần (`<script>` không thực thi).
    - Banner ở trang chi tiết kế hoạch đã duyệt: "Kế hoạch đã được duyệt. Việc thực thi lên thiết bị chưa được bật ở phiên bản này." Mục menu "Kế hoạch sửa" ẩn khi `REMEDIATION_ENABLED=0` (dùng trạng thái từ API).

---

## 10. Đặc tả frontend

Đọc code hiện có trước. Dùng `useQuery`/`useMutation` của TanStack Query; không gọi `setState` đồng bộ trong `useEffect`. Văn bản do người dùng nhập luôn hiển thị dạng thuần.

- `AuditRunPage` (bảng findings): ở finding `FAIL` của rule đủ điều kiện hiện nút **Đề xuất sửa**; rule thủ công hiện liên kết **Xem hướng dẫn** mở `ManualGuidance`. Dữ liệu đủ điều kiện lấy từ `GET /remediation/templates` (đừng hard-code danh sách rule ở frontend).
- `RemediationPreviewDialog`: xem trước (mục 9.11) và nút "Gửi đề xuất" → điều hướng tới trang chi tiết kế hoạch.
- `RemediationPlansPage` (`/remediation`): bảng kế hoạch (thiết bị, rule, rủi ro, trạng thái, người đề xuất, hạn), lọc theo trạng thái; `RemediationPlanDetailPage` (`/remediation/:planId`): xem trước đầy đủ, `PlanTimeline`, và các nút **Duyệt / Từ chối / Hủy** theo vai trò và trạng thái.
- `PlanStatusBadge`: màu và nhãn tiếng Việt cho từng trạng thái (kể cả các trạng thái đặt chỗ, phòng khi D bật).
- `SecurityEventsPage`: thêm 4 loại sự kiện mới vào `EVENT_TYPES`. `AppShell`: mục menu "Kế hoạch sửa" (operator/admin; viewer chỉ xem danh sách nếu API cho phép đọc).

---

## 11. Tài liệu `docs/remediation_workflow.md` (nội dung bắt buộc)

- Sơ đồ trạng thái (Mermaid `stateDiagram-v2`) và bảng vai trò: ai đề xuất, ai duyệt, ai hủy.
- Vì sao **AI không sinh lệnh**: lệnh chỉ đến từ mẫu cố định đã kiểm chứng; nội dung cấu hình và `evidence` là dữ liệu không đáng tin (prompt injection/chèn lệnh); allowlist so khớp chính xác; `plan_hash` ràng buộc người duyệt với đúng nội dung đã xem.
- Bảng mẫu hiện có (`NET-008`, `NET-004`): lệnh, rủi ro, tác động, khả năng hoàn tác; và lý do 6 rule còn lại chỉ có hướng dẫn thủ công.
- Phê duyệt: khác người đề xuất, nhập lại mật khẩu, hết hạn, kiểm tra lại độ mới khi duyệt; **cách thử một mình trong lab** (`NETSENTRY_REMEDIATION_REQUIRE_DISTINCT_APPROVER=0`) và vì sao không dùng khi mở ra Internet.
- Giới hạn hiện tại: chưa thực thi; mỗi (thiết bị, rule) chỉ một kế hoạch hoạt động; nhật ký chỉ-thêm trong DB không thay cho log hệ thống bất biến.
- Những gì Remediation D sẽ dùng lại: `plan_hash` so khớp trước khi chạy, `validate_commands` gọi lại ngay trước khi gửi, `persist_after_verify`, các trạng thái đặt chỗ, kỳ vọng xác minh.

---

## 12. Thứ tự thực hiện (dừng và dán output thô sau mỗi bước)

1. **Chuẩn bị**: tạo branch `feat/remediation-plan`; `pip freeze` làm mốc; liệt kê file hiện có (`wc -c`); đọc `database.py`, `AuditRunService`, entity `Finding`/`AuditRun`, `AuthService`, `require_role`/`Principal`.
2. **Domain + gói `remediation/`**: entity, lỗi, mẫu, `command_policy`, `plan_hash`, `state_machine` + test 9.1, 9.2, 9.3.
3. **Lưu trữ**: schema, `SqliteRemediationRepository` (chuyển trạng thái nguyên tử, chỉ mục một phần) + test 9.4.
4. **`AuthService.verify_password_for_user`** (refactor dùng chung với `change_password`) + test (phần step-up của 9.6) và các test `change_password` hiện có vẫn xanh.
5. **`RemediationService`**: `propose`, `approve`, `reject`, `cancel`, hết hạn lười biếng + quét khi khởi động + test 9.5, 9.6, 9.7.
6. **Cấu hình + API**: biến môi trường, routes, RBAC, sự kiện bảo mật, `/remediation/templates` + test 9.8, 9.9, 9.10.
7. **Frontend**: nút ở finding, dialog xem trước/duyệt/từ chối, trang danh sách/chi tiết, menu, `EVENT_TYPES` + test 9.11.
8. **Tài liệu** `docs/remediation_workflow.md`.
9. **Kiểm chứng tổng thể**: `bash scripts/verify_all.sh` (dán output thô), thử tay mục 13, rồi `git commit`.

---

## 13. Tiêu chí hoàn thành

- [ ] `pytest -q backend/` (từ gốc repo) xanh; tổng số test **tăng**; `npm run lint`, `typecheck`, `test`, `build` xanh; `bash scripts/verify_all.sh` xanh.
- [ ] `pip freeze` cho thấy `paramiko`, `netmiko` **không đổi** và **không có thư viện mới**.
- [ ] **Chứng minh không chạm thiết bị**: test kiến trúc xanh và bộ đếm `connect` của `FakeConnector` bằng 0 sau chu trình đề xuất → duyệt.
- [ ] Mọi lệnh trong mọi kế hoạch **bằng chính xác** một phần tử của `COMMAND_ALLOWLIST`; test chống chèn lệnh (mục 9.2) xanh.
- [ ] Mọi route mới có `require_role`; test duyệt toàn bộ `app.routes` xanh.
- [ ] Không có mật khẩu (kể cả mật khẩu xác nhận), token hay `SENTINEL_*` trong response, log, `security_events`, `remediation_events`.
- [ ] **Thử tay** (ghi kết quả vào báo cáo):
  1. Chạy audit router lab có `ip http server` (NET-008 `FAIL`). Đăng nhập `operator`, bấm **Đề xuất sửa**: xem trước hiện đúng một dòng `no ip http server`, rủi ro LOW, tác động tiếng Việt.
  2. Đăng nhập `viewer`: không thấy nút đề xuất; gọi `curl` trực tiếp `POST` nhận `403`.
  3. Đề xuất lại cho cùng thiết bị và rule: nhận `ACTIVE_PLAN_EXISTS`.
  4. Với rule `NET-001` (hoặc rule thủ công khác): chỉ có hướng dẫn, **không** có nút đề xuất.
  5. Đăng nhập `admin` **khác** người đề xuất, duyệt: nhập sai mật khẩu → `REAUTH_FAILED` (thử đủ số lần để thấy khóa tài khoản rồi mở khóa); nhập đúng → `APPROVED`, hiện hạn hiệu lực.
  6. Chính admin vừa đề xuất tự duyệt: bị `SELF_APPROVAL_NOT_ALLOWED`.
  7. Chạy audit mới trước khi duyệt một kế hoạch `PROPOSED`: duyệt nhận `PLAN_STALE`, kế hoạch chuyển `EXPIRED`.
  8. **Kiểm chứng thiết bị không bị đụng**: sau tất cả các bước, `show running-config | include http server` trên router vẫn như cũ và `show logging` không có lệnh cấu hình nào từ NetSentry.
  9. Xem `security_events`: có đủ `REMEDIATION_PROPOSED/APPROVED/REJECTED/CANCELLED`, không lộ mật khẩu.
- [ ] Có `docs/remediation_workflow.md` đủ mục 11 và báo cáo cuối liệt kê: file tạo/sửa, sai khác giữa spec và code thật, quyết định tự đưa ra, việc còn tồn đọng.

---

## 14. Để Remediation D (KHÔNG làm ở đây)

- **Thực thi**: dùng tài khoản SSH **ghi riêng** (tách khỏi tài khoản chỉ đọc), chỉ khi `NETSENTRY_REMEDIATION_EXECUTE_ENABLED=1` và **tắt hẳn khi `PUBLIC_MODE=1`**; trước khi gửi phải `validate_commands`, tính lại và so khớp `approved_plan_hash`, kiểm tra kế hoạch còn `APPROVED` chưa hết hạn, và chuyển `APPROVED → APPLYING` bằng cập nhật nguyên tử.
- **An toàn khi thực thi**: tạo điểm hoàn tác bằng cơ chế của chính thiết bị (`archive`/`configure replace`, hoặc `configure terminal revert timer`/`reload in`, tùy IOS của lab; xác minh trên router lab trước), mở rộng allowlist của Connector **chỉ** cho đúng các lệnh trong `COMMAND_ALLOWLIST`, dừng ngay nếu một lệnh bị thiết bị từ chối.
- **Xác minh**: audit lại; rule trong `expected_verification` phải chuyển `PASS` thì mới `VERIFIED` (và mới `write memory` nếu `persist_after_verify`); ngược lại `VERIFY_FAILED` và hoàn tác. Dùng findings diff của module Snapshot làm bằng chứng.
- Mở rộng mẫu sang các rule rủi ro cao hơn (VTY, SNMP, SSH) chỉ sau khi đã kiểm chứng trên lab và có cơ chế chống tự khóa.
