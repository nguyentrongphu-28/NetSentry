# NetSentry – Đặc tả Baseline đã duyệt và Phát hiện Drift cho Antigravity

> Cách dùng: lưu vào `docs/baseline_drift_spec.md`, mở Antigravity ở chế độ **Planning**, gửi: *"Đọc @docs/baseline_drift_spec.md và thực hiện đúng từng bước ở mục 11. Đưa plan trước, đợi tôi duyệt rồi mới code. Sau mỗi bước dừng lại và dán output thô."*
> Quy ước ngôn ngữ: giải thích bằng tiếng Việt; tên file/class/hàm/biến, docstring, comment, thông báo lỗi và mô tả API viết bằng tiếng Anh; **chữ hiển thị trên giao diện viết bằng tiếng Việt** (gom vào `frontend/src/i18n/strings.ts`).
> **Điều kiện đầu vào (bắt buộc):** module Auth + RBAC và module Snapshot + Diff + AI (`docs/snapshot_ai_spec.md`) đã xong, đã merge, `bash scripts/verify_all.sh` xanh. Module này **tái sử dụng** `SnapshotService`, `ConfigRedactor`, `ConfigNormalizer`, `DiffService`, `ContentDisabledError`, biến `NETSENTRY_SNAPSHOT_CONTENT_API` và hook sau audit của module đó. Nếu thiếu, **dừng và báo**. Tạo branch mới `feat/baseline-drift`.

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư full-stack senior, chuyên bảo mật ứng dụng. Hãy thêm khái niệm **baseline đã duyệt** (cấu hình chuẩn do quản trị viên phê duyệt) và **phát hiện drift** (cấu hình hiện tại lệch khỏi baseline) vào NetSentry. Module này **chỉ tính toán trên snapshot đã có**, không kết nối thêm vào thiết bị và không ghi gì xuống thiết bị.

Quy tắc bắt buộc:

1. Làm đúng thứ tự mục 11. Sau mỗi bước chạy `pytest -q backend/` **từ thư mục gốc repo** (đã `source .venv/bin/activate`) và, với bước frontend, `npm run lint`, `npm run typecheck`, `npm test`. Chỉ đi tiếp khi xanh. **Toàn bộ test hiện có phải tiếp tục xanh.**
2. Không thêm tính năng ngoài phạm vi (mục 1). Đặc tả mơ hồ hoặc mâu thuẫn → **dừng lại và hỏi**.
3. **Mỗi file `.py` vừa tạo/sửa phải chạy ngay `python -m py_compile <file>`** (từ `backend/`) trước khi chạy cả bộ test. **Ghi đè toàn bộ nội dung file**, không ghi nối (append).
4. Mỗi hành vi mới có test viết **trước**, chạy thấy thất bại, rồi mới sửa cho xanh. Tổng số test phải **tăng**.
5. Báo cáo mỗi bước chỉ gồm: danh sách file tạo/sửa, **output thô nguyên văn** của lệnh test, tổng số test trước/sau, việc chưa làm. **Không** dùng cụm "hoàn thành" khi còn lệnh chưa chạy hoặc chưa xanh. Cuối cùng đính kèm output của `bash scripts/verify_all.sh`.
6. Test không mở kết nối mạng thật; dùng `FakeConnector`. Không đụng test `live`.
7. **Không đụng vào phiên bản `netmiko` và `paramiko`; không thêm thư viện mới** (chỉ dùng thư viện chuẩn). Ghi `pip freeze` trước/sau và `diff`.
8. Sửa file hiện có chỉ ở các điểm mục 3 đánh dấu "SỬA". Không sửa Rule Engine, parser, rule, Connector, `AuditService`. **Đọc code thật** của `SnapshotService`, `AuditRunService`, parser cấu hình trước khi sửa hoặc tái sử dụng; code thật là chuẩn, sai khác với spec thì ghi vào báo cáo.
9. Không bao giờ log, trả về, hay lưu vào `security_events`: mật khẩu, credentials, session token, raw config. Mọi nội dung cấu hình trong module này là **bản đã che** của module Snapshot.
10. Python 3.11+, type hints đầy đủ; route handler viết bằng `def`. Frontend TypeScript `strict`, không `any`, không `eslint-disable` trừ khi ghi lý do cụ thể.

---

## 1. Phạm vi

**Làm**

- **Baseline**: quản trị viên chọn một snapshot (đã che) làm cấu hình chuẩn của thiết bị; mỗi thiết bị có tối đa một baseline `ACTIVE`, các baseline cũ chuyển `RETIRED` và còn trong lịch sử.
- **Drift**: so sánh snapshot hiện tại với baseline **theo khối cấu hình** (`interface ...`, `line vty ...`, `ip access-list ...`, dòng toàn cục), phân loại `ADDED`/`REMOVED`/`CHANGED`, gắn cờ **liên quan bảo mật**.
- Tự động tính và lưu **tóm tắt drift** sau mỗi lần audit thành công (để có lịch sử xu hướng).
- API (mục 7), RBAC, sự kiện bảo mật `BASELINE_APPROVED`, `BASELINE_RETIRED`.
- Bảo vệ snapshot đang làm baseline khỏi bị xóa bởi chính sách giữ tối đa N bản.
- Frontend: tab "Baseline & Drift" ở trang thiết bị, huy hiệu drift ở trang audit, hộp thoại xác nhận khi duyệt baseline còn lỗi.
- Tài liệu `docs/baseline_and_drift.md`.

**KHÔNG làm** (để giai đoạn sau)

- Tự động sửa drift, hoàn tác về baseline, đẩy baseline xuống thiết bị (đó là Giai đoạn remediation).
- Baseline theo chính sách/mẫu chung cho nhiều thiết bị, kế thừa baseline, danh sách bỏ qua do người dùng cấu hình, so sánh ngữ nghĩa (hai cấu hình khác chữ nhưng tương đương).
- Cảnh báo email/Slack, biểu đồ xu hướng phức tạp (chỉ danh sách lịch sử).
- Thay đổi hợp đồng của API hiện có (`GET /devices` giữ nguyên).

---

## 2. Ràng buộc kiến trúc

- `app/domain/`: chỉ thư viện chuẩn. `sqlite3` chỉ trong `app/repositories/`. `fastapi`/`pydantic`/`starlette` chỉ trong `app/api/` và `main.py`. `services` phụ thuộc interface, nhận qua constructor (DI); `api` chỉ gọi `services`.
- Bộ tách khối cấu hình (`config_blocks.py`) nằm ở `app/services/`, **không** import hạ tầng. Tái sử dụng parser cấu hình hiện có nếu nó đã tách được khối; nếu không, viết bộ tách riêng nhỏ gọn theo mục 8.2 (ghi vào báo cáo lý do).
- Cập nhật `tests/unit/test_architecture_imports.py` (dùng `ast`) cho các file mới.

---

## 3. Cây thư mục (chỉ file thuộc giai đoạn này)

```
backend/
  app/
    domain/
      errors.py                       # SỬA: chỉ THÊM lỗi mới (mục 4.1)
      entities/
        baseline.py                   # Baseline, BaselineStatus
        drift.py                      # BlockChange, BlockChangeKind, DriftReport, DriftSummary
        security_event.py             # SỬA: THÊM BASELINE_APPROVED, BASELINE_RETIRED
      interfaces/
        baseline_repository.py
        drift_repository.py
    repositories/
      database.py                     # SỬA: SCHEMA v4 (mục 5), user_version = 4
      sqlite_baseline_repository.py
      sqlite_drift_repository.py
    services/
      config_blocks.py                # tách cấu hình thành khối
      drift_service.py                # so sánh baseline với snapshot hiện tại
      baseline_service.py
      snapshot_service.py             # SỬA: retention bỏ qua snapshot đang làm baseline; xóa lẻ bị chặn
      audit_run_service.py            # SỬA: sau khi tạo snapshot, tính và lưu tóm tắt drift (mục 8.4)
    api/
      routes/baselines.py             # /devices/{id}/baseline(s), /devices/{id}/drift...
      schemas/baselines.py
    core/config.py                    # SỬA: biến môi trường mục 6
    main.py                           # SỬA: dựng service, router
  tests/                              # theo mục 9
frontend/
  src/
    components/baseline/BaselineCard.tsx, SetBaselineDialog.tsx, DriftSummary.tsx, DriftDetail.tsx, DriftHistory.tsx
    pages/                            # SỬA: DeviceDetailPage (tab mới), AuditRunPage (huy hiệu)
    i18n/strings.ts                   # SỬA
    types/api.ts                      # SỬA
docs/
  baseline_and_drift.md
```

---

## 4. Đặc tả domain

### 4.1 Lỗi mới (`domain/errors.py`, chỉ thêm)

```python
class BaselineNotFoundError(NetSentryError):              code = "BASELINE_NOT_FOUND"              # 404
class BaselineFailuresNotConfirmedError(NetSentryError):  code = "BASELINE_FAILURES_NOT_CONFIRMED"  # 409
class SnapshotInUseError(NetSentryError):                 code = "SNAPSHOT_IN_USE"                 # 409
class BaselineDisabledError(NetSentryError):              code = "BASELINE_DISABLED"               # 503
```

Snapshot khác thiết bị, hoặc từ audit không `COMPLETED`: dùng `DiffInputError` (422) đã có. Cập nhật `api/errors.py` ánh xạ mã HTTP.

### 4.2 Entity

```python
class BaselineStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"

@dataclass(frozen=True)
class Baseline:
    id: int
    device_id: str
    snapshot_id: int
    content_sha256: str
    status: BaselineStatus
    approved_by: str                 # username (chuỗi), không dùng khóa ngoại
    approved_at: datetime
    note: str | None                 # ≤ 200 ký tự, văn bản thuần
    fail_count_at_approval: int
    retired_at: datetime | None
    retired_by: str | None

class BlockChangeKind(str, Enum):
    ADDED = "ADDED"; REMOVED = "REMOVED"; CHANGED = "CHANGED"

@dataclass(frozen=True)
class BlockChange:
    key: str                         # vd "interface GigabitEthernet0/1", "line vty 0 4", "(global)"
    kind: BlockChangeKind
    security_relevant: bool
    added_lines: tuple[str, ...]     # rỗng khi không có quyền xem nội dung
    removed_lines: tuple[str, ...]
    added_count: int
    removed_count: int

@dataclass(frozen=True)
class DriftSummary:
    status: str                      # "IN_SYNC" | "DRIFTED"
    added_blocks: int; removed_blocks: int; changed_blocks: int
    security_relevant_count: int

@dataclass(frozen=True)
class DriftReport:
    device_id: str; baseline_id: int; run_id: int
    lines_included: bool             # false nếu chỉ trả tóm tắt
    summary: DriftSummary
    blocks: tuple[BlockChange, ...]
    truncated: bool                  # true nếu vượt DRIFT_MAX_BLOCKS
```

---

## 5. Lưu trữ (schema v4)

`init_db` idempotent. Nâng `PRAGMA user_version` 3 → 4 bằng `CREATE TABLE IF NOT EXISTS` (không đụng bảng cũ).

```sql
CREATE TABLE IF NOT EXISTS baselines (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id              TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  snapshot_id            INTEGER NOT NULL,        -- KHÔNG đặt khóa ngoại (xem ghi chú)
  content_sha256         TEXT NOT NULL,
  status                 TEXT NOT NULL CHECK (status IN ('ACTIVE','RETIRED')),
  approved_by            TEXT NOT NULL,
  approved_at            TEXT NOT NULL,
  note                   TEXT,
  fail_count_at_approval INTEGER NOT NULL,
  retired_at             TEXT,
  retired_by             TEXT
);
-- tối đa một baseline ACTIVE mỗi thiết bị
CREATE UNIQUE INDEX IF NOT EXISTS idx_baseline_active
  ON baselines(device_id) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_baseline_device ON baselines(device_id, approved_at DESC);

CREATE TABLE IF NOT EXISTS drift_results (
  run_id                  INTEGER PRIMARY KEY REFERENCES audit_runs(id) ON DELETE CASCADE,
  device_id               TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  baseline_id             INTEGER NOT NULL,
  checked_at              TEXT NOT NULL,
  status                  TEXT NOT NULL CHECK (status IN ('IN_SYNC','DRIFTED')),
  added_blocks            INTEGER NOT NULL,
  removed_blocks          INTEGER NOT NULL,
  changed_blocks          INTEGER NOT NULL,
  security_relevant_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_drift_device ON drift_results(device_id, checked_at DESC);
```

Ghi chú thiết kế: `baselines.snapshot_id` **không có khóa ngoại** vì khi xóa thiết bị, SQLite cascade xóa cả `config_snapshots` lẫn `baselines`, và hành động `RESTRICT` có thể chặn nhầm việc xóa dây chuyền đó. Tính toàn vẹn được bảo đảm ở tầng service: snapshot của baseline `ACTIVE` **không bị xóa** (mục 8.3). (Tên bảng/cột khóa ngoại phải khớp schema thật; đọc `database.py` trước.)

---

## 6. Cấu hình (`core/config.py`)

| Biến | Mặc định | Mô tả |
|---|---|---|
| `NETSENTRY_BASELINE_ENABLED` | `1` | Bật baseline/drift. Cần `NETSENTRY_SNAPSHOT_ENABLED=1`; nếu snapshot tắt thì baseline bị **ép tắt** và ghi cảnh báo khi khởi động. |
| `NETSENTRY_DRIFT_MAX_BLOCKS` | `500` | Số khối tối đa trả về mỗi báo cáo drift (1–5000); vượt thì cắt và `truncated=true`. |

Chế độ công khai (`NETSENTRY_PUBLIC_MODE=1`): **không** thêm biến mới. Hành vi: báo cáo drift mức tóm tắt (tên khối, loại thay đổi, số dòng, cờ bảo mật) vẫn dùng được; **dòng cấu hình cụ thể bị chặn** theo `NETSENTRY_SNAPSHOT_CONTENT_API` (đã bị ép về 0 ở chế độ công khai).

---

## 7. API (`/api/v1`) và phân quyền

| Phương thức | Đường dẫn | Quyền | Mô tả | Thành công | Lỗi |
|---|---|---|---|---|---|
| `GET` | `/devices/{id}/baseline` | viewer+ | Baseline `ACTIVE` | `200` | `401`, `403`, `404 BASELINE_NOT_FOUND` |
| `GET` | `/devices/{id}/baselines` | viewer+ | Lịch sử baseline (mới nhất trước) | `200` | `401`, `403`, `404` |
| `POST` | `/devices/{id}/baseline` | **admin** | Body `{snapshot_id, note?, confirm_with_failures?}`; thay baseline cũ; ghi `BASELINE_APPROVED` | `201` | `401`, `403`, `404`, `409 BASELINE_FAILURES_NOT_CONFIRMED`, `422`, `503 BASELINE_DISABLED` |
| `DELETE` | `/devices/{id}/baseline` | **admin** | Gỡ baseline `ACTIVE` (chuyển `RETIRED`); ghi `BASELINE_RETIRED` | `204` | `401`, `403`, `404` |
| `GET` | `/devices/{id}/drift?run_id=` | viewer+ | Báo cáo drift mức **tóm tắt** của một lần audit (mặc định lần mới nhất) so với baseline `ACTIVE` | `200` | `401`, `403`, `404`, `422` |
| `GET` | `/devices/{id}/drift?run_id=&detail=1` | **operator+** | Như trên kèm **dòng thay đổi**; ghi `SNAPSHOT_VIEWED` (sự kiện có sẵn) | `200` | `401`, `403`, `403 CONTENT_DISABLED`, `404`, `422` |
| `GET` | `/devices/{id}/drift/history?limit=` | viewer+ | Lịch sử tóm tắt drift (mới nhất trước, `limit` mặc định 30, tối đa 200) | `200` | `401`, `403`, `404`, `422` |

Quy tắc của `POST /baseline`:
- `snapshot_id` phải thuộc đúng thiết bị `{id}` và từ lần audit **COMPLETED**; sai → `422` (`DiffInputError`).
- Nếu lần audit đó có **ít nhất một finding `FAIL`** và `confirm_with_failures` không phải `true` → `409 BASELINE_FAILURES_NOT_CONFIRMED` (kèm số lượng FAIL trong `message`, không kèm nội dung cấu hình). Số FAIL lưu vào `fail_count_at_approval`.
- Thao tác thay baseline là **một giao dịch**: chuyển bản cũ sang `RETIRED` (ghi `retired_at`, `retired_by`) rồi tạo bản mới `ACTIVE`; nếu lỗi giữa chừng thì không còn trạng thái dở dang.
- `note` ≤ 200 ký tự, loại ký tự điều khiển, **không** render HTML ở giao diện.

Mọi route phải có `require_role(...)`; test duyệt toàn bộ `app.routes` hiện có phải tiếp tục xanh. Lỗi giữ dạng `{"error": {"code", "message"}}`. Khi `BASELINE_ENABLED=0`, `POST` trả `503 BASELINE_DISABLED`, các `GET` trả mảng rỗng/`404`, và giao diện ẩn tab.

---

## 8. Đặc tả dịch vụ

### 8.1 Nguyên tắc

Drift được tính từ **hai snapshot đã che và đã chuẩn hóa** (baseline và snapshot của lần audit đang xét). Không dùng dữ liệu khác; không kết nối thiết bị. Bí mật đã được thay bằng `<REDACTED:xxxxxx>` nên khi một bí mật đổi, dấu vân tay đổi và dòng đó hiện là thay đổi mà **không lộ giá trị**.

### 8.2 `config_blocks.py` (tách khối)

`split_blocks(text: str) -> dict[str, list[str]]` chuyển cấu hình đã chuẩn hóa thành các khối:

- **Khối có con**: dòng không thụt dòng, theo sau là các dòng thụt dòng, tạo khối với `key` = dòng tiêu đề (vd `interface GigabitEthernet0/1`, `line vty 0 4`, `ip access-list extended MGMT`, `router ospf 1`); giá trị = danh sách dòng con **giữ nguyên thứ tự** (thứ tự rất quan trọng với ACL).
- **Dòng toàn cục đơn lẻ** (không có con): gom vào khối giả `(global)`; so sánh theo **tập hợp** (thêm/xóa dòng, không xét thứ tự).
- **Banner nhiều dòng**: `banner <loại> <ký tự phân cách>` ... đến dòng chứa ký tự phân cách đóng; coi cả đoạn là **một khối** với `key` = `banner <loại>` (không để các dòng bên trong lọt vào `(global)`).
- Bỏ dòng `!`, dòng trống, và `end`. Tiêu đề trùng lặp (ví dụ hai khối cùng `key`) → ghép con theo thứ tự xuất hiện, không ném lỗi.

Giới hạn đã biết (ghi vào tài liệu): so sánh ở mức khối và dòng, **không** hiểu ngữ nghĩa; một dòng toàn cục đổi giá trị (`ip ssh version 1` → `2`) hiện là một dòng bị xóa và một dòng được thêm trong `(global)`, không phải một dòng "sửa".

### 8.3 `DriftService` và `BaselineService`

`DriftService.compare(baseline_text, current_text, include_lines)`:

- Khối chỉ có ở hiện tại → `ADDED`; chỉ có ở baseline → `REMOVED`; có ở cả hai nhưng danh sách dòng khác nhau → `CHANGED` (đếm dòng thêm/xóa bằng `difflib`; riêng `(global)` so theo tập hợp).
- `security_relevant = true` nếu `key` bắt đầu bằng một trong: `line vty`, `line con`, `line aux`, `aaa`, `username`, `enable`, `snmp-server`, `ip ssh`, `ip http`, `access-list`, `ip access-list`, `crypto`, `service`, `banner`, `ntp authentication`, `logging`; **hoặc** (với `(global)`) có dòng thêm/xóa bắt đầu bằng các tiền tố đó. Danh sách là hằng số trong code, có test.
- `include_lines=false`: các tuple dòng để rỗng, vẫn có `added_count`/`removed_count`.
- Sắp xếp kết quả: `security_relevant` trước, rồi `CHANGED` > `ADDED` > `REMOVED`, rồi theo `key`. Cắt ở `DRIFT_MAX_BLOCKS` và đặt `truncated`.
- Hai đầu vào giống hệt (`content_sha256` bằng nhau) → trả ngay `IN_SYNC` mà không tách khối.

`BaselineService`: `approve`, `retire`, `get_active`, `list_history`, `is_pinned(snapshot_id)`, `drift_for_run(device_id, run_id, detail)`, `compute_and_store_summary(device_id, run_id)`. Ghi sự kiện bảo mật ở tầng route (như spec Auth).

**Bảo vệ snapshot đang làm baseline** (SỬA `SnapshotService`):
- `enforce_retention` **không xóa** snapshot của baseline `ACTIVE`, và bản được ghim **không tính** vào số `NETSENTRY_SNAPSHOT_KEEP`.
- `DELETE /snapshots/{id}` của snapshot đang ghim → `409 SNAPSHOT_IN_USE`.
- Baseline `RETIRED` không còn ghim: snapshot của nó có thể bị xóa theo chính sách; khi đó xem lại nội dung bản cũ trả `404 SNAPSHOT_NOT_FOUND` (xử lý gọn, không lỗi 500).

### 8.4 Tích hợp vào luồng audit

Trong `AuditRunService`, **ngay sau khi tạo snapshot thành công** (điểm đã có từ module Snapshot), nếu thiết bị có baseline `ACTIVE`: gọi `compute_and_store_summary`. **Mọi lỗi ở bước này bị bắt và ghi log cảnh báo (không kèm nội dung), không bao giờ làm hỏng audit.** Không có baseline → không làm gì. Audit FAILED → không tính drift. Không thay đổi hành vi hiện có của audit.

---

## 9. Yêu cầu test

Dùng `FakeConnector`, DB và thư mục snapshot tạm (`tmp_path`). Test thất bại **trước** khi sửa (quy tắc 4).

1. **`config_blocks`**: tách đúng `interface`, `line vty`, `ip access-list` (thứ tự dòng giữ nguyên); dòng toàn cục vào `(global)`; **banner nhiều dòng** thành một khối; bỏ `!`, `end`, dòng trống; khối trùng `key` không ném lỗi; chuỗi 1 MB không treo (giới hạn thời gian).
2. **`DriftService`**: `ADDED`/`REMOVED`/`CHANGED` đúng; **đổi thứ tự dòng trong ACL được tính là thay đổi**, đổi thứ tự dòng toàn cục thì **không**; `ip ssh version 2` → `1` ra một dòng xóa và một dòng thêm trong `(global)`; cờ `security_relevant` đúng cho từng tiền tố; `include_lines=false` không trả dòng; cắt ở `DRIFT_MAX_BLOCKS`; hash bằng nhau trả `IN_SYNC`; **bí mật đổi chỉ hiện dưới dạng dấu vân tay khác, không lộ giá trị** (dùng fixture `SENTINEL_*`).
3. **Repository (SQLite thật)**: chỉ một baseline `ACTIVE` mỗi thiết bị (chỉ mục một phần); thêm baseline thứ hai `ACTIVE` cho cùng thiết bị bị từ chối ở mức DB; cascade khi xóa thiết bị (cả `baselines` lẫn `drift_results`); `drift_results` cascade khi xóa audit; truy vấn tham số hóa.
4. **`BaselineService`**: duyệt thành công; **duyệt baseline mới chuyển bản cũ sang `RETIRED` trong một giao dịch** (ép lỗi giữa chừng, không để trạng thái dở); snapshot khác thiết bị → `422`; audit không `COMPLETED` → `422`; có FAIL mà chưa xác nhận → `409` và **không tạo gì**; đã xác nhận → tạo và lưu `fail_count_at_approval`; `note` bị cắt/làm sạch.
5. **Ghim snapshot**: `enforce_retention` không xóa snapshot của baseline `ACTIVE`; bản ghim không tính vào `KEEP`; `DELETE` snapshot đang ghim → `409 SNAPSHOT_IN_USE`; baseline `RETIRED` thì snapshot bị xóa được theo retention, xem lại → `404` gọn.
6. **Luồng audit**: có baseline thì audit COMPLETED lưu một dòng `drift_results`; không có baseline thì không lưu; audit FAILED không lưu; **lỗi khi tính drift không làm hỏng audit** (ép `DriftService` ném lỗi, audit vẫn COMPLETED); `BASELINE_ENABLED=0` hoặc `SNAPSHOT_ENABLED=0` không tính gì.
7. **API và RBAC**: ma trận quyền mục 7 (mỗi vai trò × mỗi endpoint); `POST /baseline` chỉ admin; `detail=1` chỉ operator+ và ghi `SNAPSHOT_VIEWED`; ở chế độ công khai `detail=1` → `403 CONTENT_DISABLED` nhưng tóm tắt vẫn dùng được; sự kiện `BASELINE_APPROVED` và `BASELINE_RETIRED` được ghi; **không có `SENTINEL_` nào** trong response, log hay `security_events`; test duyệt toàn bộ `app.routes` vẫn xanh.
8. **Kiến trúc và cấu hình**: cập nhật `test_architecture_imports.py`; baseline bị ép tắt khi snapshot tắt (có cảnh báo); `pip freeze` không đổi; **test đối chiếu danh sách `EVENT_TYPES` của frontend với `SecurityEventType` của backend** (đã có từ module Snapshot, phải xanh sau khi thêm hai loại mới).
9. **Frontend (Vitest + MSW, qua `renderWithProviders`)**:
   - Tab "Baseline & Drift" hiện cho mọi vai trò (viewer chỉ thấy tóm tắt); nút "Đặt làm baseline" **chỉ admin**; nút "Xem chi tiết dòng" **chỉ operator/admin**.
   - Hộp thoại duyệt: khi snapshot có FAIL, hiện cảnh báo kèm số lượng và **bắt buộc tích xác nhận** mới gửi được; lỗi `409` hiển thị đúng; `note` hiển thị dạng chữ (`<script>` không thực thi).
   - `DriftSummary`: nhóm Thêm/Xóa/Thay đổi, khối `security_relevant` được làm nổi bật; trạng thái `IN_SYNC`/`DRIFTED`/"Chưa có baseline".
   - `CONTENT_DISABLED` hiện thông báo "Xem dòng cấu hình đang tắt ở chế độ công khai." `DriftHistory` hiển thị đúng thứ tự.
   - `AuditRunPage` có huy hiệu "Lệch baseline: N khối" khi `DRIFTED`.

---

## 10. Đặc tả frontend

Đọc code hiện có trước. Mọi test mới dùng `renderWithProviders`; **không** mock `AuthProvider`. Dùng `useQuery`/`useMutation` của TanStack Query; không gọi `setState` đồng bộ trong `useEffect`.

- `DeviceDetailPage`: thêm tab **Baseline & Drift** gồm `BaselineCard` (người duyệt, thời gian, ghi chú, số FAIL lúc duyệt, nút "Gỡ baseline" cho admin), `DriftSummary`, `DriftHistory` (danh sách theo thời gian), và nút "Xem chi tiết dòng" mở `DriftDetail` (unified, thêm xanh / xóa đỏ, dùng lại `DiffViewer` của module Snapshot nếu phù hợp).
- Tab **Snapshot** (module trước): thêm nút "Đặt làm baseline" trên từng dòng snapshot (admin) mở `SetBaselineDialog`; snapshot đang làm baseline có huy hiệu "Baseline" và nút Xóa bị vô hiệu kèm chú thích.
- `AuditRunPage`: huy hiệu drift nhỏ cạnh tiêu đề, bấm để mở tab Baseline & Drift.
- `SecurityEventsPage`: thêm `BASELINE_APPROVED`, `BASELINE_RETIRED` vào `EVENT_TYPES`.
- Chữ hiển thị tiếng Việt, gom vào `strings.ts`; văn bản do người dùng nhập (`note`) hiển thị dạng thuần.

---

## 11. Thứ tự thực hiện (dừng và dán output thô sau mỗi bước)

1. **Chuẩn bị**: tạo branch `feat/baseline-drift`; `pip freeze` làm mốc; liệt kê file hiện có (`wc -c`); đọc `database.py`, `SnapshotService`, `AuditRunService`, parser cấu hình; xác nhận các thành phần của module Snapshot tồn tại.
2. **Domain + `config_blocks` + `DriftService`**: entity, lỗi, tách khối, so sánh + test 9.1, 9.2.
3. **Lưu trữ**: schema v4, hai repository SQLite + test 9.3.
4. **`BaselineService` + ghim snapshot**: duyệt/gỡ, giao dịch, sửa `SnapshotService` + test 9.4, 9.5.
5. **Hook audit**: tính và lưu tóm tắt drift sau snapshot + test 9.6.
6. **Cấu hình + API**: biến môi trường, routes, RBAC, sự kiện bảo mật, hành vi chế độ công khai + test 9.7, 9.8.
7. **Frontend**: tab Baseline & Drift, dialog, huy hiệu, `EVENT_TYPES` + test 9.9.
8. **Tài liệu** `docs/baseline_and_drift.md` (mục 13).
9. **Kiểm chứng tổng thể**: `bash scripts/verify_all.sh` (dán output thô), thử tay mục 12, rồi `git commit`.

---

## 12. Tiêu chí hoàn thành

- [ ] `pytest -q backend/` (từ gốc repo) xanh; tổng số test **tăng**; `npm run lint`, `typecheck`, `test`, `build` xanh; `bash scripts/verify_all.sh` xanh.
- [ ] `pip freeze` cho thấy `paramiko`, `netmiko` **không đổi** và **không có thư viện mới**.
- [ ] Mọi route mới có `require_role`; test duyệt toàn bộ `app.routes` xanh.
- [ ] Snapshot đang làm baseline **không thể bị xóa** (cả bằng retention lẫn bằng API).
- [ ] Lỗi ở bước tính drift **không làm hỏng audit**.
- [ ] Không có `SENTINEL_*` (bí mật thử nghiệm) trong response, log, `security_events`, hay dữ liệu drift.
- [ ] **Thử tay** trên router lab (ghi kết quả vào báo cáo):
  1. Chạy audit, đăng nhập `admin`, đặt snapshot đó làm baseline (thử cả ca có FAIL: phải bị chặn cho tới khi tích xác nhận).
  2. Đổi một dòng trên router (ví dụ bật lại `ip http server`), chạy audit: tab Baseline & Drift hiện **DRIFTED**, khối `(global)` có một dòng thêm, cờ liên quan bảo mật.
  3. Đổi `enable secret`: drift chỉ hiện dấu vân tay `<REDACTED:xxxxxx>` khác, **không lộ giá trị**.
  4. Hoàn tác thay đổi, audit lại: về **IN_SYNC**; lịch sử drift có đủ các lần.
  5. Đăng nhập `viewer`: chỉ thấy tóm tắt, không có nút duyệt baseline và nút xem dòng; gọi `curl` trực tiếp `POST /baseline` nhận `403`.
  6. Chạy chế độ công khai qua `cloudflared`: tóm tắt drift dùng được, `detail=1` trả `CONTENT_DISABLED`.
  7. Thử xóa snapshot đang làm baseline: nhận `409`.
- [ ] Có `docs/baseline_and_drift.md` đủ mục 13 và báo cáo cuối liệt kê: file tạo/sửa, sai khác giữa spec và code thật, quyết định tự đưa ra, việc còn tồn đọng.

---

## 13. Tài liệu `docs/baseline_and_drift.md` (nội dung bắt buộc)

- Baseline là gì và **khi nào nên duyệt** (sau khi đã chạy audit và sửa hết lỗi, tốt nhất khi số FAIL bằng 0); ai được duyệt (admin); duyệt baseline mới làm bản cũ chuyển `RETIRED`.
- Drift được tính thế nào: theo khối, ACL tính thứ tự, dòng toàn cục tính theo tập hợp, banner là một khối; ý nghĩa cờ "liên quan bảo mật".
- **Giới hạn đã biết**: không so sánh ngữ nghĩa; một dòng toàn cục đổi giá trị hiện là một dòng xóa và một dòng thêm; cấu hình dài bất thường có thể bị cắt ở `DRIFT_MAX_BLOCKS`; drift chỉ phản ánh những gì có trong snapshot đã che.
- Hành vi ở chế độ công khai (chỉ tóm tắt, không xem dòng).
- Mối liên hệ với giai đoạn sau: khi hệ thống đã tự sửa lỗi theo kế hoạch được duyệt, cấu hình sẽ lệch baseline cũ một cách **có chủ đích**; quản trị viên cần duyệt lại baseline sau khi xác minh.

---

## 14. Để giai đoạn sau (KHÔNG làm ở đây)

- **Remediation C, D**: sinh kế hoạch sửa từ mẫu lệnh cố định, luồng `PROPOSED → APPROVED`, thực thi qua tài khoản SSH ghi riêng, xác minh bằng audit lại, hoàn tác bằng cơ chế của chính thiết bị; tắt hẳn ở chế độ công khai.
- Baseline theo chính sách dùng chung cho nhiều thiết bị, danh sách bỏ qua tùy chỉnh, so sánh ngữ nghĩa.
- Cảnh báo khi phát hiện drift liên quan bảo mật, xuất báo cáo drift (PDF/CSV).
