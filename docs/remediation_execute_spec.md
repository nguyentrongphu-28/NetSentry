# NetSentry – Đặc tả Thực thi kế hoạch sửa lỗi: Áp dụng, Xác minh và Hoàn tác (Remediation D) cho Antigravity

> Cách dùng: lưu vào `docs/remediation_execute_spec.md`, mở Antigravity ở chế độ **Planning**, gửi: *"Đọc @docs/remediation_execute_spec.md và thực hiện đúng từng bước ở mục 13. Đưa plan trước, đợi tôi duyệt rồi mới code. Sau mỗi bước dừng lại và dán output thô."*
> Quy ước ngôn ngữ: giải thích bằng tiếng Việt; tên file/class/hàm/biến, docstring, comment, thông báo lỗi và mô tả API viết bằng tiếng Anh; **chữ hiển thị trên giao diện viết bằng tiếng Việt** (gom vào `frontend/src/i18n/strings.ts`).
> **Điều kiện đầu vào (bắt buộc):** đã xong và đã merge: Auth + RBAC, **Remediation C** (`docs/remediation_plan_spec.md`) và **Snapshot + AI** (`docs/snapshot_ai_spec.md`, cần `DiffService.findings_diff`). `bash scripts/verify_all.sh` xanh. Thiếu bất kỳ mục nào → **dừng và báo**. Tạo branch mới `feat/remediation-execute`.
> **Đây là module duy nhất ghi cấu hình xuống thiết bị thật.** Mọi bước phát triển phải chạy bằng `FakeConnector`/`FakeConfigWriter`. Chỉ thử trên router **lab** ở bước cuối (mục 14), do người dùng tự thao tác.

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư full-stack senior, chuyên bảo mật ứng dụng và vận hành hệ thống mạng. Hãy thêm khả năng **thực thi có kiểm soát** một kế hoạch sửa đã được duyệt: kiểm tra trước, gửi đúng các lệnh đã duyệt, kiểm tra lại bằng audit, và hoàn tác nếu thất bại. Mọi bước phải **an toàn khi hỏng**: nếu không chắc trạng thái thiết bị, hệ thống dừng lại và đánh dấu **cần xử lý thủ công**, không tự đoán.

Nguyên tắc thiết kế xuyên suốt:

1. **Chỉ gửi đúng lệnh đã duyệt.** Lệnh đến từ mẫu cố định của Remediation C, được kiểm tra lại ngay trước khi gửi bằng `validate_commands` và so khớp `approved_plan_hash`. AI không tham gia vào bất kỳ bước nào của module này.
2. **Đường ghi tách hẳn đường đọc.** Connector chỉ-đọc hiện có **không bị sửa** (allowlist giữ nguyên, vẫn từ chối `conf t`). Đường ghi là một lớp mới (`ConfigWriter`), dùng **tài khoản SSH ghi riêng** lấy từ biến môi trường, không bao giờ từ body request.
3. **Không tin báo cáo "thành công" của chính lệnh.** Chỉ coi là xong khi một audit mới (đọc lại thiết bị) cho thấy rule đạt `PASS` và không có rule nào xấu đi.
4. **Không rõ thì dừng.** Mất kết nối giữa chừng, hoàn tác thất bại, tiến trình bị ngắt: trạng thái `FAILED` kèm cờ `needs_manual_attention`, hiển thị nổi bật, không tự thử lại.
5. **Mặc định tắt.** `NETSENTRY_REMEDIATION_EXECUTE_MODE=off`. Có chế độ `dry_run` (chạy kiểm tra, không ghi) trước chế độ `live`.

Quy tắc bắt buộc:

1. Làm đúng thứ tự mục 13. Sau mỗi bước chạy `pytest -q backend/` **từ thư mục gốc repo** (đã `source .venv/bin/activate`) và, với bước frontend, `npm run lint`, `npm run typecheck`, `npm test`. Chỉ đi tiếp khi xanh. **Toàn bộ test hiện có phải tiếp tục xanh.**
2. Không thêm tính năng ngoài phạm vi (mục 1). Đặc tả mơ hồ hoặc mâu thuẫn → **dừng lại và hỏi**.
3. **Mỗi file `.py` vừa tạo/sửa phải chạy ngay `python -m py_compile <file>`** (từ `backend/`). **Ghi đè toàn bộ nội dung file**, không ghi nối (append).
4. Mỗi hành vi mới có test viết **trước**, chạy thấy thất bại, rồi mới sửa cho xanh. Tổng số test phải **tăng**.
5. Báo cáo mỗi bước chỉ gồm: danh sách file tạo/sửa, **output thô nguyên văn** của lệnh test, tổng số test trước/sau, việc chưa làm. **Không** dùng cụm "hoàn thành" khi còn lệnh chưa chạy hoặc chưa xanh. Cuối cùng đính kèm output của `bash scripts/verify_all.sh`.
6. Unit/API test **không** mở kết nối mạng thật. Test cần router thật gắn marker `live_lab` và **bị loại mặc định** (giống test `live` hiện có); **không bao giờ chạy trong CI**.
7. **Không đổi phiên bản `netmiko` và `paramiko`; không thêm thư viện mới.** Chữ ký hàm của Netmiko phải đối chiếu với **đúng phiên bản đang cài** (`netmiko==4.8.0`) bằng `help()`/đọc mã nguồn trong venv, không dựa vào trí nhớ về phiên bản khác. Ghi `pip freeze` trước/sau.
8. Sửa file hiện có chỉ ở các điểm mục 3 đánh dấu "SỬA". **Không sửa** Rule Engine, parser, rule, `CiscoIOSConnector` (đường đọc), `AuditService`. **Đọc code thật** của `AuditRunService`, `RemediationService`, `ConnectorFactory` trước khi dùng lại; code thật là chuẩn, sai khác với spec thì ghi vào báo cáo.
9. Không bao giờ log, trả về, hay lưu vào DB/`security_events`/`remediation_events`/`step_log`: mật khẩu (kể cả mật khẩu xác nhận), SSH credentials (đọc và ghi), enable secret, session token, raw config. Đầu ra lệnh của thiết bị chỉ được lưu dạng đã làm sạch và cắt ≤ 200 ký tự.
10. Python 3.11+, type hints đầy đủ; route handler viết bằng `def`. Frontend TypeScript `strict`, không `any`, không `eslint-disable` trừ khi ghi lý do cụ thể.

---

## 1. Phạm vi

**Làm**

- `ConfigWriter` (interface) + `CiscoIOSConfigWriter` (Netmiko) + `FakeConfigWriter`, tách khỏi connector chỉ-đọc.
- `RemediationExecutor`: chuỗi bước **khóa → kiểm tra trước (audit) → ghi → xác minh (audit) → [lưu cấu hình] / hoàn tác → kiểm tra sau hoàn tác**, chạy nền, mỗi bước ghi nhật ký bền (`step_log`).
- Hai chế độ thực thi: `dry_run` (không ghi) và `live`; mặc định `off`.
- Mở rộng mẫu của Remediation C: thêm `rollback_commands`, tăng phiên bản mẫu (mục 4.2).
- Chuyển trạng thái của D (mục 4.3), cột/bảng lưu `remediation_executions`.
- Khóa theo thiết bị (mỗi thiết bị một lần thực thi tại một thời điểm), khôi phục sau sự cố tiến trình, đánh dấu cần xử lý thủ công.
- API (mục 7), RBAC, biến môi trường (mục 6), sự kiện bảo mật mới.
- Frontend: hộp thoại áp dụng, màn hình tiến trình, các biểu ngữ kết quả, danh sách "cần xử lý thủ công".
- Tài liệu `docs/remediation_execution.md` và checklist thử trên lab.

**KHÔNG làm** (để sau)

- Mẫu sửa cho `NET-001/002/003/005/006/007` hoặc bất kỳ lệnh mới ngoài allowlist.
- Cơ chế hoàn tác **trên thiết bị** (`configure replace`, `revert timer`, `reload in`): thiết kế sẵn điểm mở rộng `RollbackStrategy` nhưng **chỉ triển khai `InverseCommandsStrategy`**; các chiến lược khác cần được kiểm chứng trên IOS của lab trước.
- Thực thi nhiều kế hoạch/nhiều thiết bị cùng lúc, hàng loạt, lên lịch, tự thử lại.
- Thực thi ở chế độ công khai (**bị cấm tuyệt đối**, mục 6).
- Hoàn tác một kế hoạch đã `VERIFIED` (muốn đảo ngược thì tạo kế hoạch mới theo quy trình bình thường).
- AI trong bất kỳ bước nào.

---

## 2. Ràng buộc kiến trúc

- `netmiko`/`paramiko` chỉ trong `app/connectors/`. `CiscoIOSConfigWriter` nằm ở `app/connectors/cisco_ios_writer.py`, **không** import hay kế thừa từ `CiscoIOSConnector`; connector đọc **không** được biết tới writer.
- `RemediationExecutor` (trong `app/services/`) chỉ phụ thuộc **interface**: `ConfigWriterFactory`, `AuditRunService` (đã có), `DiffService`, `RemediationRepository`, `Clock`. **Không** import `netmiko`/`paramiko`/`socket`/`subprocess`/`urllib`, **không** import gói AI hay `app.clients`.
- Gói thuần `app/remediation/` giữ nguyên ràng buộc của Remediation C (không import connector/mạng/AI).
- `sqlite3` chỉ trong `app/repositories/`; `fastapi`/`pydantic` chỉ trong `app/api/` và `main.py`; `api` chỉ gọi `services`; route viết bằng `def`.
- Cập nhật `tests/unit/test_architecture_imports.py` (dùng `ast`) theo các ràng buộc trên.

---

## 3. Cây thư mục (chỉ file thuộc giai đoạn này)

```
backend/
  app/
    domain/
      errors.py                       # SỬA: chỉ THÊM lỗi mới (mục 4.1)
      entities/
        remediation.py                # SỬA: thêm RemediationExecution, ExecutionStep, ExecutionMode, ExecutionResult
        security_event.py             # SỬA: THÊM loại sự kiện (mục 4.5)
      interfaces/
        config_writer.py              # ConfigWriter, ConfigWriterFactory (Protocol), WriteResult
        remediation_repository.py     # SỬA: thêm phương thức cho execution
    remediation/
      templates.py                    # SỬA: thêm rollback_commands, tăng version (mục 4.2)
      command_policy.py               # SỬA: thêm ROLLBACK_COMMAND_ALLOWLIST, validate_rollback_commands
      plan_hash.py                    # SỬA: hash gồm rollback_commands
      state_machine.py                # SỬA: thêm chuyển trạng thái của D (mục 4.3)
    connectors/
      cisco_ios_writer.py             # CiscoIOSConfigWriter (Netmiko, đường ghi, tách khỏi connector đọc)
      fake_config_writer.py           # FakeConfigWriter (dùng cho test; có thể đặt trong tests/)
    factories/
      config_writer_factory.py        # tạo writer theo platform + tài khoản ghi
    repositories/
      database.py                     # SỬA: bảng remediation_executions, tăng user_version
      sqlite_remediation_repository.py  # SỬA: thêm CAS APPROVED→APPLYING có khóa thiết bị, execution CRUD
    services/
      remediation_executor.py         # RemediationExecutor + ExecutionRunner (luồng nền 1 worker)
      remediation_service.py          # SỬA: thêm apply(), lấy danh sách execution
    api/
      routes/remediation.py           # SỬA: thêm endpoint apply/executions/execution-status
      schemas/remediation.py          # SỬA
    core/config.py                    # SỬA: biến môi trường mục 6
    main.py                           # SỬA: dựng writer factory, executor, kiểm tra khởi động, quét khôi phục
  tests/                              # theo mục 10
frontend/
  src/
    components/remediation/ApplyDialog.tsx, ExecutionProgress.tsx, ExecutionResultBanner.tsx, ManualAttentionList.tsx
    pages/                            # SỬA: RemediationPlanDetailPage, RemediationPlansPage
    i18n/strings.ts, types/api.ts     # SỬA
docs/
  remediation_execution.md
```

---

## 4. Đặc tả domain

### 4.1 Lỗi mới (`domain/errors.py`, chỉ thêm)

```python
class ExecutionDisabledError(NetSentryError):     code = "EXECUTION_DISABLED"        # 503
class DeviceBusyError(NetSentryError):            code = "DEVICE_BUSY"               # 409
class PlanHashMismatchError(NetSentryError):      code = "PLAN_HASH_MISMATCH"        # 409
class ConfirmationMismatchError(NetSentryError):  code = "CONFIRMATION_MISMATCH"     # 422 (gõ sai tên thiết bị)
class WriteAuthFailedError(NetSentryError):       code = "WRITE_AUTH_FAILED"         # nội bộ (đường ghi)
class WriteRejectedError(NetSentryError):         code = "WRITE_REJECTED"            # nội bộ (thiết bị từ chối lệnh)
class WriteConnectionError(NetSentryError):       code = "WRITE_CONNECTION_FAILED"   # nội bộ
```

Các lỗi "nội bộ" không trả thẳng qua API: executor bắt chúng và ghi `failure_code` vào bản ghi thực thi. Cập nhật `api/errors.py` ánh xạ các mã trả được ra ngoài.

### 4.2 Mở rộng mẫu (`remediation/templates.py`, `command_policy.py`, `plan_hash.py`)

Thêm vào `RemediationTemplate` trường `rollback_commands: tuple[str, ...]` (mặc định rỗng).

- `NET-008`: `rollback_commands = ("ip http server",)`, `reversible=True`.
- `NET-004`: `rollback_commands = ()`, `reversible=False` (tắt dịch vụ **không** giải mã các mật khẩu đã bị mã hóa, nên không hoàn tác thực chất được).
- **Tăng `version` của cả hai mẫu lên 2.** `compute_plan_hash` thêm `rollback_commands` vào dữ liệu băm. Hệ quả có chủ đích: các kế hoạch `PROPOSED/APPROVED` tạo ở phiên bản cũ sẽ lệch hash và bị `PLAN_STALE`; ghi rõ vào tài liệu và test.
- `command_policy.py`: thêm `ROLLBACK_COMMAND_ALLOWLIST = frozenset({"ip http server"})` và `validate_rollback_commands(commands)` (cùng quy tắc so khớp chính xác như `validate_commands`). **Lệnh trong `ROLLBACK_COMMAND_ALLOWLIST` chỉ được gửi qua đường hoàn tác**, không được xuất hiện như một lệnh sửa.
- Mọi mẫu phải có test: `rollback_commands` hợp lệ theo `validate_rollback_commands`; `reversible=True` ⇒ `rollback_commands` không rỗng; `reversible=False` ⇒ rỗng.

### 4.3 Vòng đời mở rộng

Thêm vào máy trạng thái (giữ nguyên các chuyển của Remediation C):

```
APPROVED → APPLYING
APPLYING → APPLIED | FAILED
APPLIED  → VERIFIED | VERIFY_FAILED | ROLLED_BACK | FAILED
```

`VERIFIED`, `VERIFY_FAILED`, `ROLLED_BACK`, `FAILED` là **trạng thái cuối**. Ý nghĩa:

- `APPLYING`: đã khóa kế hoạch/thiết bị, đang kiểm tra trước hoặc đang ghi. **Chưa chắc đã có lệnh nào tới thiết bị.**
- `APPLIED`: **lệnh đã được gửi và thiết bị chấp nhận**, đang xác minh. Được lưu bền để phục hồi sau sự cố.
- `VERIFIED`: audit sau khi sửa xác nhận rule đạt `PASS` và không có rule nào xấu đi.
- `VERIFY_FAILED`: xác minh thất bại và **không có cách hoàn tác** (mẫu không `reversible`); thay đổi vẫn còn trên thiết bị.
- `ROLLED_BACK`: xác minh thất bại, đã hoàn tác và audit xác nhận trạng thái trở lại như trước.
- `FAILED`: mọi trường hợp còn lại (không thể kết nối, thiết bị từ chối lệnh, hoàn tác thất bại, tiến trình bị ngắt...). Kèm `failure_code` và `needs_manual_attention`.

Mọi chuyển trạng thái vẫn là **cập nhật nguyên tử** (`WHERE status = ?`, kiểm tra `rowcount == 1`).

### 4.4 Entity thực thi

```python
class ExecutionMode(str, Enum):  DRY_RUN = "dry_run"; LIVE = "live"
class ExecutionResult(str, Enum):
    RUNNING = "RUNNING"; DRY_RUN_OK = "DRY_RUN_OK"; VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"; ROLLED_BACK = "ROLLED_BACK"; FAILED = "FAILED"

@dataclass(frozen=True)
class ExecutionStep:
    step: str          # PRECHECK_AUDIT | WRITE | POST_AUDIT | SAVE_CONFIG | ROLLBACK | POST_ROLLBACK_AUDIT | DRY_RUN_PREVIEW
    status: str        # STARTED | OK | FAILED | SKIPPED
    at: datetime
    detail: str | None # ≤ 200 ký tự, đã làm sạch, không bí mật

@dataclass(frozen=True)
class RemediationExecution:
    id: int; plan_id: int; mode: ExecutionMode
    started_at: datetime; finished_at: datetime | None; started_by: str
    result: ExecutionResult
    failure_code: str | None
    changes_sent: bool                 # đã có lệnh nào được thiết bị chấp nhận chưa
    pre_run_id: int | None; post_run_id: int | None; rollback_run_id: int | None
    persist_status: str                # NOT_REQUESTED | SAVED | FAILED
    needs_manual_attention: bool
    steps: tuple[ExecutionStep, ...]
```

### 4.5 Sự kiện bảo mật mới (thêm vào `SecurityEventType`)

`REMEDIATION_APPLY_STARTED`, `REMEDIATION_VERIFIED`, `REMEDIATION_ROLLED_BACK`, `REMEDIATION_FAILED`, `REMEDIATION_DRY_RUN`. **Frontend `EVENT_TYPES` phải khớp**; test đối chiếu frontend/backend đã có phải xanh.

---

## 5. Lưu trữ

`init_db` idempotent; tăng `PRAGMA user_version` lên **giá trị kế tiếp** (đọc `database.py`). Đặt chỗ sẵn từ Remediation C nên **không cần đổi** bảng `remediation_plans`.

```sql
CREATE TABLE IF NOT EXISTS remediation_executions (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id                INTEGER NOT NULL REFERENCES remediation_plans(id) ON DELETE CASCADE,
  mode                   TEXT NOT NULL CHECK (mode IN ('dry_run','live')),
  started_at             TEXT NOT NULL,
  finished_at            TEXT,
  started_by             TEXT NOT NULL,
  result                 TEXT NOT NULL CHECK (result IN
        ('RUNNING','DRY_RUN_OK','VERIFIED','VERIFY_FAILED','ROLLED_BACK','FAILED')),
  failure_code           TEXT,
  changes_sent           INTEGER NOT NULL DEFAULT 0,
  pre_run_id             INTEGER,
  post_run_id            INTEGER,
  rollback_run_id        INTEGER,
  persist_status         TEXT NOT NULL DEFAULT 'NOT_REQUESTED'
        CHECK (persist_status IN ('NOT_REQUESTED','SAVED','FAILED')),
  needs_manual_attention INTEGER NOT NULL DEFAULT 0,
  steps_json             TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_exec_plan ON remediation_executions(plan_id, id);
CREATE INDEX IF NOT EXISTS idx_exec_attention ON remediation_executions(needs_manual_attention) WHERE needs_manual_attention = 1;
```

Khóa theo thiết bị khi vào `APPLYING` (một cập nhật nguyên tử duy nhất, trong một giao dịch):

```sql
UPDATE remediation_plans SET status='APPLYING', updated_at=?
 WHERE id=? AND status='APPROVED'
   AND NOT EXISTS (SELECT 1 FROM remediation_plans
                    WHERE device_id=? AND status IN ('APPLYING','APPLIED'));
```

`rowcount == 0` thì phân biệt (đọc lại) giữa kế hoạch không còn `APPROVED` (`InvalidTransitionError`) và thiết bị đang bận (`DeviceBusyError`). `run_id` không có khóa ngoại (như Remediation C); `pre_run_id/post_run_id/rollback_run_id` cũng **không** đặt khóa ngoại để giữ vết. (Tên bảng/cột phải khớp schema thật.)

---

## 6. Cấu hình (`core/config.py`)

| Biến | Mặc định | Mô tả |
|---|---|---|
| `NETSENTRY_REMEDIATION_EXECUTE_MODE` | `off` | `off` / `dry_run` / `live`. Giá trị khác → từ chối khởi động. `off`: `POST /apply` trả `503 EXECUTION_DISABLED`. |
| `NETSENTRY_SSH_WRITE_USERNAME` | rỗng | Tài khoản SSH **dùng riêng cho ghi cấu hình**. |
| `NETSENTRY_SSH_WRITE_PASSWORD` | rỗng | Mật khẩu của tài khoản ghi. |
| `NETSENTRY_SSH_WRITE_ENABLE_SECRET` | rỗng | Enable secret của tài khoản ghi (nếu cần). |
| `NETSENTRY_REMEDIATION_ALLOW_SHARED_ACCOUNT` | `0` | Cho phép tài khoản ghi **trùng** với tài khoản đọc. Mặc định cấm; chỉ bật trong lab, có cảnh báo trong log. |
| `NETSENTRY_REMEDIATION_STEP_TIMEOUT_SECONDS` | `60` | Hết thời gian chờ mỗi bước SSH (10–300). |
| `NETSENTRY_REMEDIATION_EXECUTION_TIMEOUT_MINUTES` | `15` | Quá thời gian này mà bản ghi vẫn `RUNNING` thì quét khôi phục đánh dấu `FAILED` + cần xử lý thủ công (5–120). |
| `NETSENTRY_REMEDIATION_APPLY_RATE_LIMIT` | `5/3600` | Tối đa 5 lần `apply` mỗi giờ **mỗi người dùng**. |

Điều kiện khởi động (vi phạm → ghi lỗi rõ ràng và dừng):

1. `EXECUTE_MODE != off` đòi `NETSENTRY_REMEDIATION_ENABLED=1` (module C đang bật).
2. `EXECUTE_MODE = live` đòi đủ `SSH_WRITE_USERNAME` và `SSH_WRITE_PASSWORD`; và `SSH_WRITE_USERNAME` **khác** `NETSENTRY_SSH_USERNAME` trừ khi `ALLOW_SHARED_ACCOUNT=1`.
3. `EXECUTE_MODE` cần cả credentials **đọc** (`NETSENTRY_SSH_USERNAME/PASSWORD`) vì kiểm tra trước/xác minh là audit đọc; thiếu → từ chối khởi động.
4. **`NETSENTRY_PUBLIC_MODE=1` kết hợp `EXECUTE_MODE != off` → từ chối khởi động** (`RuntimeError`, thông báo nói rõ). Không âm thầm ép về `off`.
5. Credentials ghi **không bao giờ** được đọc từ request, đưa vào response, log, `security_events` hay `step_log`.

---

## 7. API (`/api/v1`) và phân quyền

| Phương thức | Đường dẫn | Quyền | Mô tả | Thành công | Lỗi |
|---|---|---|---|---|---|
| `POST` | `/remediation-plans/{plan_id}/apply` | **admin** | Body `{password, confirm_device_id}`; chế độ do **server** quyết định (client không chọn `live`/`dry_run`) | `202` + `{plan_id, execution_id, mode}` | `401`, `403 USER_SESSION_REQUIRED`, `404`, `409 INVALID_TRANSITION/PLAN_EXPIRED/PLAN_STALE/PLAN_HASH_MISMATCH/DEVICE_BUSY`, `422 REAUTH_FAILED/CONFIRMATION_MISMATCH`, `429`, `503 EXECUTION_DISABLED` |
| `GET` | `/remediation-plans/{plan_id}/executions` | viewer+ | Các lần thực thi kèm `steps` (dùng để theo dõi tiến trình) | `200` | `401`, `403`, `404` |
| `GET` | `/remediation/execution-status` | viewer+ | `{mode, write_account_configured, runner_busy}`; **không** trả tên/mật khẩu tài khoản | `200` | `401`, `403` |
| `GET` | `/remediation/attention` | viewer+ | Danh sách kế hoạch `FAILED` có `needs_manual_attention=true` chưa được ghi nhận xử lý | `200` | `401`, `403` |
| `POST` | `/remediation-plans/{plan_id}/acknowledge` | **admin** | Ghi nhận đã xử lý thủ công; body `{note}` ≤ 200 ký tự; chỉ hợp lệ khi `needs_manual_attention` | `204` | `401`, `403`, `404`, `409`, `422` |

Quy tắc:

- Mọi route phải có `require_role(...)`; test duyệt toàn bộ `app.routes` hiện có phải tiếp tục xanh. Lỗi giữ dạng `{"error": {"code", "message"}}`.
- Chỉ **phiên người dùng thật** mới gọi được `apply`/`acknowledge` (không `api_key`, không `disabled`): `403 USER_SESSION_REQUIRED`.
- `apply` trả `202` ngay sau khi **khóa** và **đưa vào hàng đợi**; công việc chạy nền (mục 8). Giao diện theo dõi bằng `GET .../executions`.
- Cột "đã ghi nhận" cho `acknowledge`: thêm `acknowledged_by/at/note` vào `remediation_executions` hoặc bảng phụ (chọn cách đơn giản nhất, ghi vào báo cáo); sự kiện `remediation_events` được ghi, không ghi đè lịch sử.

---

## 8. Đặc tả dịch vụ

### 8.1 `ConfigWriter` và `CiscoIOSConfigWriter`

```python
class ConfigWriter(Protocol):
    def __enter__(self) -> "ConfigWriter": ...
    def __exit__(self, *exc) -> None: ...                     # luôn đóng phiên
    def apply(self, commands: Sequence[str]) -> WriteResult: ...   # gửi từng lệnh một
    def save_config(self) -> None: ...                         # write memory, chỉ gọi sau khi VERIFIED
```

`CiscoIOSConfigWriter` (Netmiko; **đối chiếu API với `netmiko==4.8.0` đã cài**):

- Chỉ nhận tài khoản ghi do factory đưa vào (từ biến môi trường); phải ở chế độ privileged (enable) trước khi vào cấu hình.
- `apply`: **kiểm tra từng lệnh** bằng `validate_commands` hoặc `validate_rollback_commands` (tùy ngữ cảnh do executor truyền) **ngay trước khi gửi**, một dòng một lần; không bao giờ nối nhiều lệnh thành một chuỗi; luôn thoát chế độ cấu hình trong `finally`. Lệnh nằm ngoài cả hai allowlist → `CommandNotAllowedError` **trước khi chạm thiết bị**.
- Phát hiện lỗi: mọi dòng đầu ra bắt đầu bằng `%` (vd `% Invalid input`, `% Incomplete`, `% Ambiguous`, `% Authorization failed`, `% Access denied`) → `WriteRejectedError`; sai tài khoản → `WriteAuthFailedError`; hết thời gian/ngắt kết nối → `WriteConnectionError`. `WriteResult` ghi từng lệnh: `accepted: bool`, `output_excerpt` (làm sạch, ≤ 200 ký tự).
- `save_config`: gửi đúng `write memory` (hằng trong lớp, **không** nhận chuỗi từ ngoài). Lỗi → `WriteRejectedError`/`WriteConnectionError`.
- `FakeConfigWriter`: ghi lại các lệnh nhận được, có thể lập trình để thất bại ở lệnh/bước chỉ định, **ném lỗi nếu bị gọi trong dry-run** (để test chứng minh dry-run không ghi).
- Kiểm tra bất biến (test 10.1): connector đọc hiện có **vẫn từ chối** `conf t`, `no ip http server` và mọi lệnh cấu hình; `app/connectors/` chứa hai lớp độc lập.

### 8.2 `RemediationExecutor` (luồng thực thi)

Chạy nền trong `ExecutionRunner` (một `ThreadPoolExecutor(max_workers=1)`: tối đa **một** lần thực thi trên toàn hệ thống). Trạng thái bền nằm trong DB; thread chỉ thực hiện, không giữ trạng thái duy nhất trong bộ nhớ. Mọi ngoại lệ không lường trước được bắt ở lớp ngoài cùng: kế hoạch chuyển `FAILED` + `needs_manual_attention` (không bao giờ treo ở `APPLYING`/`APPLIED`).

**Kiểm tra đồng bộ trong request `apply`** (trước khi đưa vào hàng đợi):

1. `EXECUTE_MODE != off`; principal là phiên admin thật; rate limit theo người dùng.
2. `confirm_device_id` phải **bằng chính xác** `device_id` của kế hoạch (`ConfirmationMismatchError`).
3. Nạp kế hoạch; quá hạn → `EXPIRED` + `PlanExpiredError`; phải `APPROVED`.
4. **Chống sửa đổi**: tính lại `plan_hash` từ mẫu hiện hành; phải bằng **cả** `plan_hash` lẫn `approved_plan_hash` đã lưu (khác → `PlanHashMismatchError`, không đổi trạng thái); `validate_commands` và `validate_rollback_commands` phải qua.
5. **Xác nhận lại danh tính** (step-up) bằng `AuthService.verify_password_for_user` (đã có từ Remediation C); sai → `ReauthFailedError`.
6. Chế độ `live`: cập nhật nguyên tử `APPROVED → APPLYING` kèm khóa thiết bị (mục 5); lỗi → `InvalidTransitionError`/`DeviceBusyError`. Chế độ `dry_run`: **không đổi trạng thái kế hoạch** (vẫn `APPROVED`); vẫn kiểm tra thiết bị không bận.
7. Tạo bản ghi `remediation_executions` (`RUNNING`), ghi `remediation_events` và `security_events` (`REMEDIATION_APPLY_STARTED` hoặc `REMEDIATION_DRY_RUN`), đưa công việc vào hàng đợi, trả `202`.

**Các bước của luồng nền (`live`):** mỗi bước ghi `ExecutionStep` `STARTED` rồi `OK`/`FAILED` vào `steps_json` **ngay khi xảy ra** (để giao diện theo dõi và để phục hồi).

1. **`PRECHECK_AUDIT`**: chạy một audit bình thường bằng credentials **đọc** (dùng `AuditRunService`, tạo audit run, snapshot, findings như thường lệ). Ghi `pre_run_id`. Điều kiện: audit `COMPLETED` và finding của `rule_id` đang `FAIL`. Không đạt → `FAILED` (`changes_sent=false`, `failure_code = PRECHECK_FAILED` hoặc `PRECHECK_NOT_FAILING`), **không gọi writer**.
2. **`WRITE`**: mở `ConfigWriter`, `apply(plan.commands)`. Thiết bị chấp nhận hết → ghi `changes_sent=true`, chuyển `APPLYING → APPLIED` (cập nhật nguyên tử). Lỗi ở lệnh đầu tiên → `FAILED` (`changes_sent=false`). Lỗi ở lệnh thứ k>1 sau khi các lệnh trước đã được chấp nhận → ghi `changes_sent=true`, chuyển `APPLIED` và đi thẳng tới bước hoàn tác (mục dưới) với lý do `WRITE_PARTIAL`.
3. **`POST_AUDIT`**: chạy audit đọc lần hai, ghi `post_run_id`. **Xác minh thành công** khi *tất cả*: audit `COMPLETED` (chứng tỏ SSH vẫn dùng được); rule trong `expected_verification` có `status == PASS`; `DiffService.findings_diff(pre_run, post_run)` **không có** `REGRESSION` ở bất kỳ rule nào.
4. **Thành công** → cập nhật `APPLIED → VERIFIED`, `result=VERIFIED`. Nếu `persist_after_verify`: bước **`SAVE_CONFIG`** gọi `writer.save_config()`; thành công → `persist_status=SAVED`; thất bại → `persist_status=FAILED`, **vẫn `VERIFIED`** nhưng ghi cảnh báo (cấu hình mới chưa được lưu vào startup-config). Ghi `REMEDIATION_VERIFIED`.
5. **Xác minh thất bại** (rule chưa `PASS`, hoặc có `REGRESSION`):
   - Mẫu **`reversible`** → bước **`ROLLBACK`**: `apply(template.rollback_commands)` qua đường hoàn tác; rồi **`POST_ROLLBACK_AUDIT`** (audit đọc lần ba, ghi `rollback_run_id`): trạng thái được coi là đã khôi phục khi audit `COMPLETED` và rule trở lại như `pre_run` (không có `REGRESSION` so với `pre_run`). Đạt → `APPLIED → ROLLED_BACK` (ghi `REMEDIATION_ROLLED_BACK`). Không đạt hoặc hoàn tác lỗi → `FAILED`, `needs_manual_attention=true`, `failure_code = ROLLBACK_FAILED` hoặc `ROLLBACK_UNVERIFIED`.
   - Mẫu **không `reversible`** → `APPLIED → VERIFY_FAILED` (`needs_manual_attention=true`; thay đổi vẫn còn trên thiết bị; giao diện nêu rõ).
6. **Không thể kiểm chứng** (audit sau khi ghi không kết nối được hoặc lỗi): thử hoàn tác một lần nếu mẫu `reversible` (cố gắng tốt nhất), nhưng dù thành công hay không vẫn chuyển `APPLIED → FAILED` với `failure_code = POST_AUDIT_UNAVAILABLE` và `needs_manual_attention=true` (không có bằng chứng về trạng thái thật). **Không** tự coi là đã hoàn tác.

Mọi đường dẫn `FAILED` có `changes_sent=true` hoặc không rõ đều đặt `needs_manual_attention=true` và ghi `REMEDIATION_FAILED`.

**Dry-run:** chạy `PRECHECK_AUDIT` thật (đọc), sau đó bước `DRY_RUN_PREVIEW` ghi lại **đúng các lệnh sẽ được gửi** và các điều kiện sẽ kiểm tra; **không** mở `ConfigWriter`, **không** audit sau. Kết thúc `result=DRY_RUN_OK` (hoặc `FAILED` nếu kiểm tra trước thất bại); kế hoạch **vẫn `APPROVED`**. Ghi `REMEDIATION_DRY_RUN`.

### 8.3 Phục hồi sau sự cố

- Khi khởi động (và định kỳ lười biếng khi đọc): các bản ghi `RUNNING` cũ hơn `EXECUTION_TIMEOUT_MINUTES` được đóng lại: kế hoạch đang `APPLYING` → `FAILED` (`failure_code=INTERRUPTED`, `changes_sent` **không rõ** nên đặt `needs_manual_attention=true`); đang `APPLIED` → `FAILED` (`INTERRUPTED_AFTER_WRITE`, `needs_manual_attention=true`, thông điệp nói rõ "lệnh đã được gửi nhưng chưa xác minh"). **Không tự thử lại.** Mỗi trường hợp ghi `remediation_events` và `REMEDIATION_FAILED`.
- `acknowledge` (admin) gỡ cờ khỏi danh sách "cần xử lý" sau khi người vận hành đã kiểm tra thiết bị; không đổi trạng thái kế hoạch.

---

## 9. Đặc tả frontend

Đọc code hiện có trước. Dùng `useQuery`/`useMutation`/`refetchInterval` của TanStack Query; không gọi `setState` đồng bộ trong `useEffect`. Mọi test dùng `renderWithProviders`; **không** mock `AuthProvider`.

- `RemediationPlanDetailPage`: bỏ biểu ngữ "chưa bật thực thi" của Remediation C; khi kế hoạch `APPROVED`, trạng thái thực thi `mode != off` và người dùng là admin, hiện nút **Áp dụng lên thiết bị** (nhãn **Chạy thử (dry-run)** khi `mode=dry_run`). Dữ liệu `mode` lấy từ `GET /remediation/execution-status`; không hard-code.
- `ApplyDialog`: hiển thị lại **đúng từng dòng lệnh**, thiết bị, mức rủi ro, lệnh hoàn tác (nếu có) hoặc cảnh báo **không thể hoàn tác**; bắt buộc: gõ lại **tên thiết bị** (`confirm_device_id`), nhập **mật khẩu**, tích xác nhận. Nút gửi vô hiệu cho tới khi đủ điều kiện. Mật khẩu **không** lưu vào storage và bị xóa khỏi state sau khi gửi. Xử lý `DEVICE_BUSY`, `PLAN_HASH_MISMATCH`, `PLAN_EXPIRED`, `PLAN_STALE`, `REAUTH_FAILED`, `CONFIRMATION_MISMATCH`, `EXECUTION_DISABLED`, `429`.
- `ExecutionProgress`: sau khi `202`, thăm dò `GET .../executions` (mỗi 2 giây; dừng khi `result != RUNNING`); hiển thị các bước theo thứ tự (Kiểm tra trước, Gửi lệnh, Xác minh, Lưu cấu hình / Hoàn tác) với biểu tượng trạng thái và mô tả ngắn; văn bản thuần.
- `ExecutionResultBanner`: một biểu ngữ cho từng kết quả: **VERIFIED** (xanh, kèm liên kết "So sánh trước/sau" mở `ComparePanel` giữa `pre_run_id` và `post_run_id`; ghi chú nếu `persist_status=FAILED`), **DRY_RUN_OK** (xanh nhạt, liệt kê lệnh sẽ gửi), **ROLLED_BACK** (vàng), **VERIFY_FAILED** (cam, thay đổi vẫn còn), **FAILED** (đỏ; nếu `needs_manual_attention` có khối cảnh báo lớn "Cần kiểm tra thiết bị thủ công" kèm gợi ý lệnh `show running-config | include ...` lấy từ mẫu, **không** gợi ý lệnh ghi).
- `RemediationPlansPage`: đầu trang có `ManualAttentionList` (lấy từ `GET /remediation/attention`, nổi bật màu đỏ) với nút **Đã xử lý** (admin, mở hộp thoại ghi chú). Mục menu hiển thị chấm đỏ khi có mục cần xử lý.
- `SecurityEventsPage`: thêm 5 loại sự kiện mới vào `EVENT_TYPES`.
- Viewer/operator không thấy nút áp dụng; operator vẫn xem được tiến trình.

---

## 10. Yêu cầu test

Dùng DB tạm (`tmp_path`), `Clock` giả, `FakeConnector` có thể lập trình **chuỗi kết quả theo thứ tự lần gọi** (cấu hình trước có `ip http server`, sau khi ghi không có), `FakeConfigWriter`. Test thất bại **trước** khi sửa (quy tắc 4).

1. **Mẫu, hash, allowlist**: `rollback_commands` hợp lệ; `reversible` khớp `rollback_commands`; hash đổi khi đổi `rollback_commands`; kế hoạch tạo ở `version` 1 bị `PLAN_STALE`/`PLAN_HASH_MISMATCH`; `validate_rollback_commands` từ chối mọi dòng ngoài allowlist; **lệnh hoàn tác không dùng được như lệnh sửa** và ngược lại.
2. **`CiscoIOSConfigWriter`** (đối tượng Netmiko giả/mock, không mạng): chỉ gửi lệnh qua allowlist, **một dòng một lần**; lệnh ngoài allowlist (`reload`, `no ip http server\nreload`, `conf t`) bị từ chối **trước khi gửi**; đầu ra bắt đầu bằng `%` → `WriteRejectedError`; sai xác thực/hết giờ/ngắt kết nối → đúng loại lỗi; luôn thoát chế độ cấu hình trong `finally`; `save_config` chỉ gửi `write memory`; đầu ra lưu lại đã làm sạch và ≤ 200 ký tự; **credentials không xuất hiện trong bất kỳ lỗi/log nào** (`SENTINEL_*`). **Connector đọc vẫn từ chối mọi lệnh cấu hình.**
3. **Khóa và chuyển trạng thái (SQLite thật)**: `APPROVED → APPLYING` nguyên tử; **hai `apply` đồng thời trên cùng kế hoạch chỉ một thành công**; hai kế hoạch **khác rule cùng thiết bị** → thứ hai nhận `DEVICE_BUSY`; thiết bị khác nhau không chặn nhau; mọi trạng thái cuối bất biến; chuyển trái phép (vd `APPROVED → VERIFIED`) → `InvalidTransitionError`.
4. **Luồng `live` thành công**: pre `FAIL` → ghi → post `PASS`, không `REGRESSION` → `VERIFIED`; writer nhận **đúng** `plan.commands` (không hơn, không kém); có đủ `pre_run_id`, `post_run_id`; `steps` đúng thứ tự; ba sự kiện bảo mật/nhật ký tương ứng; `persist_after_verify=True`: `save_config` chỉ gọi **sau** `VERIFIED` (kiểm tra thứ tự gọi); lưu thất bại → vẫn `VERIFIED`, `persist_status=FAILED`; `persist_after_verify=False` không gọi `save_config`.
5. **Kiểm tra trước thất bại**: rule đã `PASS` → `FAILED` (`PRECHECK_NOT_FAILING`), `changes_sent=false`, **writer không bao giờ được gọi**, `needs_manual_attention=false`; audit trước không kết nối được → `FAILED` (`PRECHECK_FAILED`), writer không gọi.
6. **Lỗi khi ghi**: lệnh đầu bị thiết bị từ chối → `FAILED`, `changes_sent=false`, không hoàn tác, không cần xử lý thủ công; sai mật khẩu ghi → `FAILED` (`WRITE_AUTH_FAILED`), thiết bị không bị đụng; mất kết nối trong lúc ghi lệnh → trạng thái `FAILED` + `needs_manual_attention=true` (không chắc trạng thái).
7. **Xác minh thất bại và hoàn tác**: rule vẫn `FAIL` sau khi ghi (mẫu `reversible`) → hoàn tác bằng đúng `rollback_commands` → audit thứ ba khớp `pre_run` → `ROLLED_BACK`; **`REGRESSION` ở rule khác** cũng kích hoạt hoàn tác; mẫu **không `reversible`** (NET-004) → `VERIFY_FAILED` + cần xử lý thủ công, **không** gọi writer lần hai; hoàn tác lỗi → `FAILED` (`ROLLBACK_FAILED`) + cần xử lý thủ công; audit sau hoàn tác không khớp → `FAILED` (`ROLLBACK_UNVERIFIED`); audit sau khi ghi không kết nối được → cố gắng hoàn tác một lần rồi `FAILED` (`POST_AUDIT_UNAVAILABLE`) + cần xử lý thủ công, **không** tự coi là đã hoàn tác.
8. **Dry-run**: `FakeConfigWriter` **ném lỗi nếu bị gọi**, test vẫn xanh (chứng minh không ghi); kế hoạch vẫn `APPROVED`; bản ghi `DRY_RUN_OK` chứa đúng lệnh sẽ gửi; `PRECHECK_AUDIT` đã chạy; dry-run không giữ khóa thiết bị sau khi xong.
9. **Kiểm tra đồng bộ của `apply`**: `EXECUTE_MODE=off` → `503`; sai `confirm_device_id` → `422`; sai mật khẩu → `REAUTH_FAILED` (tăng bộ đếm, khóa khi đủ lần, mật khẩu không lộ); kế hoạch quá hạn → `EXPIRED`; **hash lệch** (mẫu đổi version, hoặc sửa trực tiếp `commands_json`/`approved_plan_hash` trong DB) → `PLAN_HASH_MISMATCH` và **không đổi trạng thái, writer không được gọi**; không phải admin/principal `api_key`/`disabled` → `403`; rate limit theo người dùng → `429`.
10. **Phục hồi sự cố**: bản ghi `RUNNING` quá hạn (dùng `Clock` giả): kế hoạch `APPLYING` → `FAILED` (`INTERRUPTED`), `APPLIED` → `FAILED` (`INTERRUPTED_AFTER_WRITE`), cả hai `needs_manual_attention=true`; **không tự thử lại**; bản ghi chưa quá hạn không bị đụng; ngoại lệ bất ngờ trong luồng nền → kế hoạch `FAILED` chứ không treo.
11. **Cấu hình khởi động**: `PUBLIC_MODE=1` + `EXECUTE_MODE=live` hoặc `dry_run` → từ chối khởi động; `live` thiếu credentials ghi → từ chối; tài khoản ghi trùng tài khoản đọc → từ chối (trừ khi `ALLOW_SHARED_ACCOUNT=1`, có cảnh báo); thiếu credentials đọc → từ chối; giá trị `EXECUTE_MODE` lạ → từ chối; `EXECUTE_MODE != off` mà `REMEDIATION_ENABLED=0` → từ chối.
12. **API và RBAC**: ma trận quyền mục 7 (mỗi vai trò × mỗi endpoint); test duyệt toàn bộ `app.routes` vẫn xanh; `execution-status` không lộ tên/mật khẩu tài khoản; `acknowledge` chỉ khi `needs_manual_attention`; **không có `SENTINEL_*`** (mật khẩu, credentials đọc/ghi, enable secret) trong response, log, `security_events`, `remediation_events`, `steps_json`; các sự kiện `REMEDIATION_APPLY_STARTED/VERIFIED/ROLLED_BACK/FAILED/DRY_RUN` được ghi đúng lúc.
13. **Kiến trúc**: cập nhật `test_architecture_imports.py`: `netmiko`/`paramiko` chỉ trong `app/connectors/`; `cisco_ios_writer.py` và `cisco_ios.py` (đọc) không import lẫn nhau; `remediation_executor.py` không import `netmiko`/`paramiko`/`socket`/`subprocess`/`urllib`/gói AI/`app.clients`; gói `app/remediation/` vẫn thuần; `pip freeze` không đổi (**đặc biệt `netmiko==4.8.0`, `paramiko==5.1.0`**); test đối chiếu `EVENT_TYPES` frontend/backend xanh.
14. **Frontend (Vitest + MSW, qua `renderWithProviders`)**: nút áp dụng chỉ cho admin và chỉ khi kế hoạch `APPROVED` và `mode != off`; nhãn "Chạy thử" khi `dry_run`; `ApplyDialog` yêu cầu gõ đúng tên thiết bị + mật khẩu + tích xác nhận (nút vô hiệu trước khi đủ), hiển thị đúng từng lệnh và cảnh báo không hoàn tác được với NET-004, mật khẩu không vào storage; xử lý đủ các mã lỗi mục 9; `ExecutionProgress` thăm dò và dừng đúng lúc (MSW trả chuỗi `RUNNING → ... → VERIFIED`); `ExecutionResultBanner` đúng cho từng kết quả, `FAILED` + `needs_manual_attention` hiện khối cảnh báo lớn; `ManualAttentionList` ở đầu trang với nút **Đã xử lý** chỉ admin; văn bản do máy chủ/người dùng trả về hiển thị dạng thuần (`<script>` không thực thi).
15. **Test lab thật (marker `live_lab`, loại mặc định, không chạy trong CI)**: kịch bản NET-008 trên router lab, cấu hình qua biến môi trường; **không bao giờ chạy tự động**.

---

## 11. Tài liệu `docs/remediation_execution.md` (nội dung bắt buộc)

- Sơ đồ luồng (Mermaid `sequenceDiagram`) từ `apply` đến `VERIFIED/ROLLED_BACK/FAILED`; sơ đồ trạng thái đầy đủ.
- **Mô hình an toàn**: chỉ lệnh trong allowlist, đường ghi tách đường đọc, kiểm tra hash ngay trước khi gửi, xác minh bằng audit chứ không bằng đầu ra lệnh, không tự thử lại, `needs_manual_attention`.
- **Chuẩn bị tài khoản ghi trên router lab**: tạo người dùng riêng, quyền tối thiểu cần để vào cấu hình (nêu rõ giới hạn: bản MVP cần quyền privileged; có thể giới hạn bằng `privilege configure level` hoặc AAA/command authorization nếu lab hỗ trợ, và việc này chưa được kiểm chứng ở đây), hạn chế nguồn truy cập VTY chỉ cho máy chủ NetSentry, **xoay vòng mật khẩu sau mỗi lần demo**.
- **Ghi chú lab (bắt buộc điền)**: kết quả `show version | include Version|uptime`, `show privilege`, `show archive` của router lab. Không chặn phát triển nhưng **cần cho giai đoạn sau** khi cân nhắc cơ chế hoàn tác trên thiết bị.
- Hoàn tác hiện chỉ dựa vào **lệnh đảo ngược** do mẫu định nghĩa; giải thích vì sao các mẫu hiện có không thể làm mất kết nối SSH và vì sao các rule rủi ro cao (VTY, SSH, SNMP) **chưa** có mẫu: chúng cần cơ chế hoàn tác trên thiết bị đã được kiểm chứng.
- Bảng biến môi trường mục 6, ba chế độ `off/dry_run/live`, vì sao **cấm tuyệt đối ở chế độ công khai**.
- Cách xử lý khi có mục "cần xử lý thủ công": các lệnh `show` để kiểm tra, cách đưa thiết bị về trạng thái mong muốn, cách ghi nhận bằng nút **Đã xử lý**.
- Khắc phục sự cố: `DEVICE_BUSY`, `PLAN_HASH_MISMATCH`, `WRITE_AUTH_FAILED`, `POST_AUDIT_UNAVAILABLE`, tiến trình bị ngắt giữa chừng.

---

## 12. Rủi ro còn lại (ghi vào tài liệu và báo cáo cuối)

- Hoàn tác bằng lệnh đảo ngược **không** khôi phục được trạng thái nếu thiết bị đã thay đổi theo cách khác trong lúc đó; `NET-004` không hoàn tác được.
- Nếu mất kết nối giữa lúc ghi và lúc xác minh, hệ thống **không** biết trạng thái thật; chỉ cảnh báo, không đoán.
- Tài khoản ghi có quyền cao trên thiết bị: bảo vệ biến môi trường, xoay vòng mật khẩu, giới hạn nguồn truy cập.
- Chưa có cơ chế hoàn tác phía thiết bị: các rule rủi ro cao chưa được hỗ trợ.

---

## 13. Thứ tự thực hiện (dừng và dán output thô sau mỗi bước)

1. **Chuẩn bị**: tạo branch `feat/remediation-execute`; `pip freeze` làm mốc; liệt kê file hiện có (`wc -c`); đọc `AuditRunService`, `RemediationService`, `ConnectorFactory`, `CiscoIOSConnector`; **xác minh API Netmiko trong venv** (`python -c "import netmiko; help(netmiko.ConnectHandler.send_config_set)"` và các hàm sẽ dùng) rồi ghi chữ ký thực tế vào báo cáo.
2. **Domain + mẫu mở rộng**: lỗi, entity, `rollback_commands`, tăng version, hash, máy trạng thái, `ROLLBACK_COMMAND_ALLOWLIST` + test 10.1, 10.3 (phần máy trạng thái thuần).
3. **Lưu trữ**: bảng `remediation_executions`, CAS khóa thiết bị, CRUD execution + test 10.3 (SQLite thật).
4. **Đường ghi**: `ConfigWriter`, `CiscoIOSConfigWriter` (mock Netmiko), `FakeConfigWriter`, factory + test 10.2 và phần kiến trúc của 10.13.
5. **`RemediationExecutor` luồng `live`**: các bước, xác minh, hoàn tác, đường lỗi + test 10.4, 10.5, 10.6, 10.7.
6. **Dry-run và phục hồi sự cố** + test 10.8, 10.10.
7. **Cấu hình, `apply` đồng bộ, API, RBAC, sự kiện** + test 10.9, 10.11, 10.12, 10.13.
8. **Frontend**: `ApplyDialog`, `ExecutionProgress`, biểu ngữ kết quả, `ManualAttentionList`, `EVENT_TYPES` + test 10.14.
9. **Tài liệu** `docs/remediation_execution.md`.
10. **Kiểm chứng tổng thể (tự động)**: `bash scripts/verify_all.sh` (dán output thô). **Dừng tại đây và chờ người dùng thử trên lab (mục 14).** Chỉ `git commit` sau khi người dùng xác nhận kết quả thử lab.

---

## 14. Thử trên router lab (do NGƯỜI DÙNG thực hiện, theo đúng thứ tự)

Chuẩn bị: ghi `show version`, `show privilege`, `show archive` vào `docs/remediation_execution.md`; tạo tài khoản ghi riêng; có sẵn truy cập console/phương án khôi phục riêng ngoài SSH; **sao lưu cấu hình thủ công** (`show running-config` lưu tại máy cá nhân, không commit).

1. **`off`**: khởi động với `EXECUTE_MODE=off`, bấm áp dụng trên kế hoạch đã duyệt → nhận `EXECUTION_DISABLED`, router không đổi.
2. **`dry_run`** (`NETSENTRY_REMEDIATION_EXECUTE_MODE=dry_run`): đề xuất và duyệt kế hoạch NET-008 trên router có `ip http server`; chạy thử: kết quả `DRY_RUN_OK`, liệt kê đúng `no ip http server`; **kiểm tra `show running-config | include http server` vẫn như cũ** và `show logging` không có lệnh cấu hình nào từ NetSentry.
3. **`live` NET-008, trường hợp thành công**: sau khi chạy, `VERIFIED`; `show running-config | include http server` hiện `no ip http server`; SSH vẫn dùng được; so sánh trước/sau chỉ có NET-008 chuyển `FIXED`, không `REGRESSION`; `security_events` có đủ sự kiện; **không có mật khẩu nào** trong log/DB.
4. **Lưu cấu hình**: lặp lại với `persist_after_verify` bật (đặt lại `ip http server` trước); xác nhận `show startup-config | include http server` chỉ đổi **sau** `VERIFIED`. Khôi phục cấu hình lab sau đó.
5. **Lỗi ghi (diễn tập)**: tạm đặt sai mật khẩu ghi; áp dụng: nhận `FAILED` (`WRITE_AUTH_FAILED`), `changes_sent=false`, router **không** đổi, **không** có cờ cần xử lý thủ công.
6. **Bận thiết bị**: bấm áp dụng hai kế hoạch (hai rule khác nhau) liên tiếp trên cùng thiết bị: một cái nhận `DEVICE_BUSY`.
7. **Chế độ công khai**: khởi động với `PUBLIC_MODE=1` và `EXECUTE_MODE=live` → ứng dụng **từ chối khởi động**.
8. **NET-004** (nếu muốn): lưu ý nó **không hoàn tác được**; chạy một lần và ghi lại kết quả.
9. Dọn dẹp: khôi phục cấu hình lab, **đổi/xóa mật khẩu tài khoản ghi**, đặt lại `EXECUTE_MODE=off`.

Đường hoàn tác (`ROLLED_BACK`) và các đường `FAILED` do mất kết nối **không thử trực tiếp được trên lab một cách an toàn**; chúng được kiểm chứng bằng test với writer/connector giả (mục 10.5–10.7). Ghi rõ điều này trong báo cáo cuối.

---

## 15. Tiêu chí hoàn thành

- [ ] `pytest -q backend/` (từ gốc repo) xanh; tổng số test **tăng**; `npm run lint`, `typecheck`, `test`, `build` xanh; `bash scripts/verify_all.sh` xanh.
- [ ] `pip freeze` cho thấy `netmiko==4.8.0`, `paramiko==5.1.0` **không đổi** và **không có thư viện mới**.
- [ ] Connector đọc **không bị sửa** và vẫn từ chối mọi lệnh cấu hình (test xanh).
- [ ] Mọi lệnh gửi tới `ConfigWriter` nằm trong allowlist, được kiểm tra **trước khi gửi**; hash được so khớp **ngay trước khi gửi**; ghi chỉ xảy ra sau xác nhận mật khẩu và gõ đúng tên thiết bị.
- [ ] `dry_run` không bao giờ gọi writer (test chứng minh); chế độ công khai **không khởi động được** với `dry_run`/`live`.
- [ ] Mọi đường lỗi kết thúc ở một trạng thái cuối rõ ràng; **không có trạng thái nào treo ở `APPLYING`/`APPLIED`** (kể cả sau sự cố tiến trình); các trường hợp không chắc có `needs_manual_attention`.
- [ ] Không có mật khẩu, credentials (đọc/ghi), enable secret hay `SENTINEL_*` trong response, log, DB, `security_events`, `remediation_events`, `steps_json`.
- [ ] Người dùng đã thực hiện đủ mục 14 trên lab và ghi kết quả; ghi chú lab (`show version`, `show privilege`, `show archive`) đã có trong tài liệu.
- [ ] Có `docs/remediation_execution.md` đủ mục 11 và báo cáo cuối liệt kê: file tạo/sửa, chữ ký Netmiko thực tế đã dùng, sai khác giữa spec và code thật, quyết định tự đưa ra, việc còn tồn đọng, các rủi ro còn lại (mục 12).

---

## 16. Để giai đoạn sau (KHÔNG làm ở đây)

- **Hoàn tác phía thiết bị** (`archive`/`configure replace`, `configure terminal revert timer`, `reload in`) dưới dạng `RollbackStrategy` mới, **chỉ** sau khi đã kiểm chứng cơ chế trên đúng IOS của lab; điều kiện để mở rộng mẫu sang VTY/SSH/SNMP.
- Mẫu sửa mới (mỗi mẫu đi kèm: lệnh cố định, lệnh đảo ngược, kiểm tra không tự khóa, test, thử lab).
- Thực thi theo lịch, hàng loạt, nhiều thiết bị song song; thông báo email/Slack; xuất báo cáo kiểm toán thay đổi.
- Hoàn tác thủ công một kế hoạch đã `VERIFIED` bằng kế hoạch đảo ngược.
