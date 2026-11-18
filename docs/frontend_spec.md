# NetSentry – Đặc tả Frontend Dashboard (React + Vite + TypeScript) cho Antigravity

> Cách dùng: lưu vào `docs/frontend_spec.md`, mở Antigravity ở chế độ **Planning**, gửi: *"Đọc @docs/frontend_spec.md và thực hiện đúng từng bước ở mục 9. Đưa plan trước, đợi tôi duyệt rồi mới code. Không ghi đè file không rỗng mà chưa hỏi."*
> Quy ước ngôn ngữ: giải thích trong tài liệu bằng tiếng Việt; **tên file/biến/hàm/component, comment code viết bằng tiếng Anh; chữ hiển thị trên giao diện viết bằng tiếng Việt** (gom hết vào một file chuỗi, mục 4.7).
> Điều kiện đầu vào: backend (Rule Engine, Connector, AuditService, SQLite, REST API) đã xong và đã kiểm chứng trên router thật. **Hãy tạo branch mới (`feat/frontend`) trước khi bắt đầu.**

---

## 0. Vai trò và cách làm việc

Bạn là kỹ sư frontend senior. Hãy xây **dashboard web** trong `frontend/` để người dùng quản lý thiết bị, chạy audit và xem kết quả (findings) bằng cách gọi REST API NetSentry có sẵn.

Quy tắc bắt buộc:

1. Làm đúng thứ tự mục 9. Sau mỗi bước chạy `npm run lint`, `npm run typecheck`, `npm test` (và `npm run build` ở các bước có nêu), chỉ đi tiếp khi xanh.
2. **Không sửa backend** (`backend/`). Nếu phát hiện API thiếu hoặc lỗi, ghi vào báo cáo, không tự sửa. Chỉ được **thêm** file dev-only trong `scripts/` (mục 6.2).
3. Không thêm tính năng ngoài phạm vi (mục 1). Đặc tả mơ hồ hoặc mâu thuẫn → **dừng lại và hỏi**.
4. **Không đoán hình dạng JSON của API.** Trước khi viết type, đọc `backend/app/api/schemas/*.py`, `backend/app/api/routes/*.py` và `docs/api_and_persistence.md`; nếu có thể, chạy API dev (mục 6.2) rồi đọc `/openapi.json`. Mọi sai khác giữa đặc tả này và code backend thật → **code backend thật là chuẩn**, ghi sai khác vào báo cáo.
5. Trước khi tạo file, liệt kê các file đã có trong `frontend/` kèm `wc -c`. File **0 byte** được ghi đè; file **không rỗng** thì hỏi trước.
6. TypeScript chế độ `strict`, không dùng `any` (dùng `unknown` + kiểm tra kiểu khi cần).
7. Không bao giờ ghi password, enable secret, API key vào: URL, `localStorage`, cookie, `console.*`, thông báo lỗi, tên query key, snapshot test, hay file nào trong repo.
8. Phụ thuộc: ghim phiên bản chính xác trong `package.json` (không dùng `^`/`~`), commit `package-lock.json`, chọn phiên bản đã phát hành **ít nhất 14 ngày**, dùng `npm ci` để cài. Không thêm thư viện UI lớn (MUI, Ant Design, Chakra…).

---

## 1. Phạm vi

**Làm**

- Màn hình nhập API key (kết nối), đăng xuất.
- **Dashboard thiết bị**: thẻ tổng hợp, danh sách thiết bị kèm kết quả audit gần nhất.
- Thêm / xóa thiết bị.
- **Chạy audit** (hộp thoại nhập credentials hoặc dùng credentials mặc định của server).
- Trang chi tiết thiết bị: thông tin, lịch sử audit có phân trang.
- Trang chi tiết lần audit: tiêu đề tóm tắt + bảng findings có lọc, sắp xếp, mở rộng xem bằng chứng/khuyến nghị.
- Trạng thái loading/rỗng/lỗi, responsive, khả năng truy cập (a11y) cơ bản.
- Test (Vitest + Testing Library + MSW), lint, typecheck, tài liệu `docs/frontend.md`.

**KHÔNG làm**

- Không AI giải thích finding, không thực thi remediation (chỉ hiển thị văn bản hướng dẫn), không snapshot/diff cấu hình, không biểu đồ xu hướng, không tài khoản/phân quyền người dùng, không đa ngôn ngữ chuyển đổi, không dark mode, không SSR/PWA, không WebSocket, không Docker.
- Không phục vụ bản build từ FastAPI, không sửa CORS/backend.

---

## 2. Công nghệ

| Hạng mục | Lựa chọn |
|---|---|
| Build | Vite + React + TypeScript (`strict`) |
| Routing | `react-router-dom` (v6 trở lên) |
| Gọi API + cache | `@tanstack/react-query` (không dùng Devtools trong bản build production) |
| Styling | Tailwind CSS (không dùng thư viện component ngoài; tự viết `Button`, `Badge`, `Modal`, `Table`…) |
| Icon | `lucide-react` (tuỳ chọn) |
| Test | Vitest + `@testing-library/react` + `@testing-library/user-event` + `msw` + `jsdom` |
| Lint | ESLint (cấu hình TypeScript + React hooks + jsx-a11y) |

Node: dùng phiên bản LTS mà môi trường của bạn đang có (ghi rõ trong `docs/frontend.md` và `engines` của `package.json`).

---

## 3. Cách frontend nối với API (rất quan trọng)

- API chạy ở `127.0.0.1:8000` trên server và **chỉ bind localhost**. Frontend gọi API bằng **đường dẫn tương đối** (`/api/v1/...`, `/health`) và dùng **proxy của Vite** (cả `server.proxy` lẫn `preview.proxy`) chuyển tới `VITE_API_PROXY_TARGET` (mặc định `http://127.0.0.1:8000`). Nhờ vậy cùng origin → **không cần CORS**, không sửa backend.
- Quy trình dev khuyến nghị (không cần cài Node trên server): trên máy dev mở tunnel `ssh -L 8000:127.0.0.1:8000 user@server`, chạy `npm run dev` ở máy dev; trình duyệt vào `http://localhost:5173`.
- Xác thực: mọi request (trừ `/health`) gửi header `X-API-Key`. Key do người dùng nhập ở màn hình kết nối.
- **Lưu key**: chỉ `sessionStorage` (tên khoá `netsentry.apiKey`), tự mất khi đóng tab. Không dùng `localStorage`, không đặt key vào URL. Có nút "Đăng xuất" xóa key và xóa cache của react-query.
- Mọi lỗi từ API có dạng `{"error": {"code": "...", "message": "...", "details"?: [...]}}`. Client phải phân tích dạng này; lỗi mạng/timeout/không đúng dạng → lỗi chung.
- Thời gian chờ (`AbortController`): 15 giây cho request thường, **120 giây** cho `POST /devices/{id}/audit`.

---

## 4. Đặc tả chức năng

### 4.1 Cây thư mục

```
frontend/
  package.json  package-lock.json  tsconfig.json  vite.config.ts  vitest.config.ts
  eslint.config.js  postcss.config.js  tailwind.config.js  index.html  .env.example
  src/
    main.tsx  App.tsx  index.css
    types/api.ts                    # type mô tả JSON của API (theo code backend thật)
    i18n/strings.ts                 # toàn bộ chữ tiếng Việt
    services/
      apiClient.ts                  # fetch wrapper: header, timeout, parse lỗi, 401
      devicesApi.ts  auditsApi.ts
    hooks/
      useApiKey.tsx                 # context + sessionStorage
      useDevices.ts  useDevice.ts  useAuditRuns.ts  useAuditRun.ts
      useRunAudit.ts  useCreateDevice.ts  useDeleteDevice.ts
    utils/format.ts                 # định dạng thời gian, thứ tự severity/status
    components/
      ui/  Button.tsx Badge.tsx Modal.tsx Spinner.tsx EmptyState.tsx ErrorBanner.tsx Card.tsx
      layout/ AppShell.tsx
      devices/ DeviceTable.tsx SummaryTiles.tsx AddDeviceDialog.tsx DeleteDeviceDialog.tsx RunAuditDialog.tsx
      audits/ AuditHistoryTable.tsx FindingsTable.tsx FindingRow.tsx StatusBadge.tsx SeverityBadge.tsx AuditSummaryHeader.tsx
    pages/
      ConnectPage.tsx  DevicesPage.tsx  DeviceDetailPage.tsx  AuditRunPage.tsx  NotFoundPage.tsx
    test/ setup.ts  msw/handlers.ts  msw/server.ts  fixtures.ts
scripts/
  run_api_with_fake_device.py       # dev-only, mục 6.2
docs/
  frontend.md
```

`.gitignore` (gốc repo): thêm `frontend/node_modules/`, `frontend/dist/`, `frontend/.env.local`, `frontend/coverage/`.

### 4.2 Điều hướng

| Đường dẫn | Trang | Yêu cầu |
|---|---|---|
| `/connect` | `ConnectPage` | Công khai |
| `/` | `DevicesPage` | Cần API key |
| `/devices/:deviceId` | `DeviceDetailPage` | Cần API key |
| `/audits/:runId` | `AuditRunPage` | Cần API key |
| `*` | `NotFoundPage` | – |

Chưa có key → chuyển về `/connect`. Bất kỳ request nào trả **401** → xóa key, xóa cache, chuyển về `/connect` kèm thông báo "Khóa API không hợp lệ hoặc đã hết hiệu lực". `deviceId`/`runId` trong URL phải được `encodeURIComponent`/kiểm tra là số (với `runId`); sai → `NotFoundPage`.

### 4.3 Màn hình kết nối (`ConnectPage`)

- Ô nhập API key (`type="password"`, `autoComplete="off"`), nút "Kết nối".
- Khi bấm: lưu tạm key, gọi `GET /api/v1/devices`. Thành công → lưu vào `sessionStorage` và chuyển tới `/`. 401 → "Khóa API không đúng". Lỗi mạng → "Không kết nối được tới máy chủ API".
- Hiển thị trạng thái máy chủ qua `GET /health` (không cần key): chấm xanh/đỏ + phiên bản.

### 4.4 Dashboard (`DevicesPage`)

- **Thẻ tổng hợp** (`SummaryTiles`, tính ở client từ danh sách thiết bị): tổng số thiết bị; thiết bị chưa audit; thiết bị có lần audit gần nhất `FAILED` (lỗi kết nối); thiết bị có ít nhất 1 finding FAIL; tổng số finding FAIL ở các lần audit gần nhất.
- **Bảng thiết bị** (`DeviceTable`): cột `device_id`/tên (liên kết sang chi tiết), host:port, nền tảng, lần audit gần nhất (thời gian tương đối + tooltip thời gian đầy đủ), kết quả (huy hiệu trạng thái run + số PASS/FAIL/UNKNOWN), hành động ("Chạy audit", "Xóa"). Thiết bị chưa audit hiển thị "Chưa audit".
- Nút "Thêm thiết bị" (mở `AddDeviceDialog`).
- Trạng thái: loading (skeleton/spinner), rỗng (có nút thêm thiết bị), lỗi (banner + nút "Thử lại").
- Tự làm mới khi cửa sổ lấy lại focus (mặc định react-query); **không** polling.

### 4.5 Thêm / xóa thiết bị

- `AddDeviceDialog`: các trường `device_id`, `host`, `name` (tuỳ chọn), `port` (mặc định 22), nền tảng cố định `cisco_ios` (chỉ hiển thị, không cho chọn khác). Kiểm tra ở client giống backend: `device_id` khớp `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, `port` 1–65535, `host` không rỗng, không chứa khoảng trắng hoặc `/`. Lỗi từ server (409 `DEVICE_EXISTS`, 422 `INVALID_DEVICE`/`VALIDATION_ERROR` kèm `details`) hiển thị gần đúng trường. Thành công → đóng hộp thoại và làm mới danh sách.
- `DeleteDeviceDialog`: xác nhận, nêu rõ "xóa thiết bị và toàn bộ lịch sử audit". 404 xem như đã xóa (làm mới danh sách).

### 4.6 Chạy audit (`RunAuditDialog`)

- Hai lựa chọn (radio): **"Dùng thông tin đăng nhập mặc định của máy chủ"** (không gửi body) hoặc **"Nhập thông tin đăng nhập"** (`username`, `password`, `enable_secret` tuỳ chọn; gửi `{"credentials": {...}}`; để trống `enable_secret` thì gửi `null` hoặc bỏ khóa theo đúng schema backend).
- Trường mật khẩu: `type="password"`, `autoComplete="new-password"`, không có nút "hiện mật khẩu" ghi nhớ.
- **Quản lý bí mật trong bộ nhớ**: credentials chỉ nằm trong state của hộp thoại. Sau khi mutation kết thúc (thành công hoặc lỗi) hoặc khi đóng hộp thoại: xóa state mật khẩu và gọi `mutation.reset()` để react-query không giữ `variables`. Không đưa credentials vào query key, URL, log, hay `title`/`aria-label`.
- Khi đang chạy: nút bị khóa (chống bấm đúp), hiện spinner và dòng "Đang kết nối thiết bị, có thể mất vài chục giây…". Có nút "Đóng" (chỉ đóng giao diện; ghi chú: *audit vẫn tiếp tục chạy trên máy chủ*). Quá 120 giây → báo "Hết thời gian chờ"; người dùng có thể xem kết quả sau trong lịch sử.
- Kết quả: `201` → chuyển sang `/audits/{id}` dù `status` là `COMPLETED` hay `FAILED`. Với `FAILED`, trang chi tiết hiển thị `error_code` + `error_message` cùng gợi ý tiếng Việt theo mã (mục 4.7).
- Lỗi: `409 AUDIT_ALREADY_RUNNING` → "Thiết bị đang được audit"; `422 CREDENTIALS_REQUIRED` → gợi ý chuyển sang nhập thủ công; `404` → "Thiết bị không còn tồn tại".
- Sau khi xong: vô hiệu hóa/làm mới cache `devices`, `device`, `auditRuns`.

### 4.7 Chuỗi giao diện (`i18n/strings.ts`)

Gom toàn bộ chữ tiếng Việt vào một file (không rải trong component). Có bảng gợi ý theo `error_code`:

| error_code | Gợi ý hiển thị |
|---|---|
| `AUTH_FAILED` | Sai tên đăng nhập, mật khẩu hoặc enable secret. |
| `CONNECT_TIMEOUT` | Không kết nối được tới thiết bị (hết thời gian chờ hoặc bị từ chối). Kiểm tra IP, firewall, dịch vụ SSH. |
| `CONNECT_FAILED` | Lỗi SSH khi kết nối (thuật toán mã hóa không tương thích, rớt kết nối…). |
| `COLLECTION_FAILED` | Không lấy được cấu hình (thiếu quyền privileged hoặc lệnh bị từ chối). |
| `COMMAND_NOT_ALLOWED` | Lệnh bị chặn bởi danh sách lệnh chỉ-đọc. |
| `UNSUPPORTED_PLATFORM` | Nền tảng thiết bị chưa được hỗ trợ. |
| `INTERNAL_ERROR` | Lỗi nội bộ. Xem log máy chủ. |

Mã lạ → hiển thị mã nguyên văn + `message` từ server.

### 4.8 Trang chi tiết thiết bị (`DeviceDetailPage`)

- Thông tin thiết bị (id, tên, host, port, nền tảng, ngày tạo) và nút "Chạy audit".
- **Lịch sử audit** (`AuditHistoryTable`): thời gian, trạng thái, số PASS/FAIL/UNKNOWN, liên kết sang chi tiết; phân trang dùng `limit`/`offset`/`total` (mặc định 20, nút Trước/Sau, hiển thị "x–y / total").
- Phía trên bảng: tóm tắt lần audit gần nhất.

### 4.9 Trang chi tiết audit (`AuditRunPage`)

- `AuditSummaryHeader`: thiết bị, hostname, nền tảng, bắt đầu/kết thúc/thời lượng, trạng thái, số PASS/FAIL/UNKNOWN. Run `FAILED` → khối lỗi nổi bật (mục 4.6) và không có bảng findings.
- `FindingsTable` (dùng dữ liệu của `GET /audits/{id}`, lọc ở client vì chỉ vài chục dòng): cột Rule, Tiêu đề, Trạng thái, Mức độ. Bộ lọc theo trạng thái (Tất cả/FAIL/UNKNOWN/PASS) và mức độ. **Mặc định sắp xếp**: FAIL → UNKNOWN → PASS, trong cùng nhóm theo mức độ giảm dần (CRITICAL > HIGH > MEDIUM > LOW > INFO), cuối cùng theo `rule_id`.
- Bấm một dòng để **mở rộng** (`aria-expanded`): hiển thị `evidence` (mỗi dòng một dòng, font monospace, cuộn ngang), `rationale`, `remediation` (nút "Sao chép"), `verification`. Kèm ghi chú cố định: *"Đây chỉ là hướng dẫn. NetSentry không tự thay đổi cấu hình thiết bị."*
- Mọi chuỗi lấy từ API (evidence, title…) được render bằng React (tự escape); **cấm `dangerouslySetInnerHTML`**.

### 4.10 Huy hiệu, định dạng

- `StatusBadge` (PASS xanh, FAIL đỏ, UNKNOWN vàng/xám; run: COMPLETED/FAILED) và `SeverityBadge`: **luôn có chữ**, không chỉ dựa vào màu (a11y).
- `utils/format.ts`: thời gian theo `Intl.DateTimeFormat("vi-VN")`, thời gian tương đối bằng `Intl.RelativeTimeFormat("vi")`, thời lượng; hằng số thứ tự severity/status dùng chung.

### 4.11 Khả năng truy cập và responsive

- Nhãn `<label>` cho mọi ô nhập; hộp thoại `role="dialog"`, `aria-modal`, **khóa focus trong hộp thoại**, đóng bằng `Esc`, trả focus về nút mở.
- Điều hướng bằng bàn phím; hàng mở rộng được dùng `button`, không dùng `div onClick`.
- Bố cục dùng được từ ~360px: bảng cuộn ngang trong container riêng, không làm cuộn ngang cả trang.

---

## 5. Hợp đồng với API (đối chiếu code backend thật trước khi dùng)

Prefix `/api/v1` (trừ `/health`). Header `X-API-Key` bắt buộc trừ `/health`.

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/health` | `{"status","version"}`, không cần key |
| POST | `/devices` | 201; lỗi 409/422 |
| GET | `/devices` | `{"items":[thiết bị + latest_audit|null]}` |
| GET | `/devices/{device_id}` | 200/404 |
| DELETE | `/devices/{device_id}` | 204/404 |
| POST | `/devices/{device_id}/audit` | body tuỳ chọn `{"credentials":{...}}`; 201 cả khi run `FAILED`; 404/409/422 |
| GET | `/devices/{device_id}/audits?limit=&offset=` | `{"items","total","limit","offset"}` |
| GET | `/audits/{run_id}` | chi tiết + findings |
| GET | `/audits/{run_id}/findings?status=&severity=` | (không dùng ở client trong giai đoạn này) |

`types/api.ts` phải khớp **đúng** tên trường và cấu trúc (phẳng hay lồng `summary`/`findings`) trong schema backend. Thêm hàm kiểm tra kiểu đơn giản (type guard) cho phản hồi lỗi `{"error": {...}}`.

---

## 6. Môi trường dev và dữ liệu thử

### 6.1 `vite.config.ts`

- `server.proxy` và `preview.proxy`: `/api` và `/health` → `loadEnv`/`process.env.VITE_API_PROXY_TARGET` (mặc định `http://127.0.0.1:8000`).
- `server.host` mặc định `127.0.0.1` (không mở ra mạng LAN).
- `.env.example` chỉ chứa `VITE_API_PROXY_TARGET=http://127.0.0.1:8000`. **Không bao giờ** đặt API key vào biến `VITE_*` (biến này bị nhúng vào bản build).

### 6.2 `scripts/run_api_with_fake_device.py` (chỉ để phát triển)

- Khởi chạy API thật (`create_app`) với `ConnectorFactory` đăng ký `FakeConnector` nạp `backend/tests/fixtures/configs/ios_insecure.cfg` cho nền tảng `cisco_ios`; DB SQLite tạm trong thư mục tạm; bind `127.0.0.1:8000`; **tự sinh API key ngẫu nhiên và in ra terminal**; in cảnh báo "DEV ONLY – dữ liệu giả".
- Biến môi trường `NETSENTRY_SSH_USERNAME`/`NETSENTRY_SSH_PASSWORD` giả được đặt trong tiến trình để thử luồng "dùng credentials mặc định".
- Cho phép chọn fixture qua tham số (`--fixture secure|insecure|minimal`).
- Không sửa file nào trong `backend/`.

---

## 7. Yêu cầu test

MSW giả lập API; không gọi mạng thật. Mỗi test độc lập, dùng thời gian giả khi cần.

1. **`apiClient`**: gửi `X-API-Key` đúng; không gửi key cho `/health`; parse lỗi `{"error":...}`; lỗi mạng/timeout → lỗi chung; 401 kích hoạt đăng xuất; timeout 120s riêng cho audit.
2. **Kết nối**: key đúng → vào dashboard và lưu vào `sessionStorage` (không phải `localStorage`); key sai → thông báo lỗi; chưa có key vào `/` → chuyển `/connect`; đăng xuất xóa key + cache.
3. **Dashboard**: thẻ tổng hợp tính đúng từ dữ liệu mẫu (có thiết bị chưa audit, run FAILED, run có FAIL); trạng thái loading/rỗng/lỗi + nút thử lại.
4. **Thêm thiết bị**: kiểm tra hợp lệ phía client (id, port, host); hiển thị 409 và 422 theo trường; thành công làm mới danh sách.
5. **Chạy audit**:
   - chế độ mặc định không gửi body; chế độ thủ công gửi đúng body;
   - bấm đúp chỉ tạo **một** request;
   - sau khi xong (thành công và lỗi) hoặc đóng hộp thoại, ô mật khẩu trống và `mutation.reset()` đã gọi (kiểm tra qua DOM/hành vi);
   - 201 + `FAILED` vẫn điều hướng và hiển thị gợi ý đúng theo `error_code`; 409/422/404 hiển thị đúng thông báo;
   - **bảo mật**: mật khẩu giả `FAKE-UI-PW` không xuất hiện trong URL, `sessionStorage`, `localStorage`, `console.*` (spy), hay trong DOM sau khi đóng hộp thoại.
6. **Findings**: thứ tự sắp xếp mặc định đúng; lọc theo trạng thái và mức độ; mở rộng hiển thị evidence/remediation; `aria-expanded` đúng; nút sao chép gọi clipboard; nội dung chứa `<script>` hoặc `<img onerror>` được hiển thị như chữ thường (không thực thi).
7. **Lịch sử audit**: phân trang `limit/offset/total` đúng, nút Trước/Sau bị khóa ở đầu/cuối.
8. **a11y cơ bản**: hộp thoại giữ focus và đóng bằng `Esc`; huy hiệu luôn có chữ; không dùng `dangerouslySetInnerHTML` (kiểm tra bằng test quét mã nguồn hoặc rule ESLint).
9. **Bảo mật cấu hình**: không file nào dùng `localStorage`, `VITE_` chứa key; kiểm tra bằng test quét mã nguồn (grep) ở `src/`.
10. `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` đều xanh; cảnh báo `npm audit` mức high/critical phải được báo cáo.

---

## 8. Chất lượng giao diện

- Thiết kế sạch, nhất quán: lưới 4/8px, một bảng màu trung tính + màu nhấn, huy hiệu màu theo ngữ nghĩa (đỏ/xanh/vàng), chữ dễ đọc, độ tương phản đạt AA.
- Trạng thái trống có hướng dẫn hành động; thông báo lỗi nói rõ nguyên nhân và bước tiếp theo.
- Không dùng animation nặng; spinner đơn giản; không nhảy bố cục khi tải dữ liệu.
- Nếu có trình duyệt trong Antigravity, chụp ảnh các màn hình chính (kết nối, dashboard, hộp thoại audit, chi tiết audit có FAIL, chi tiết audit FAILED) với dữ liệu từ `run_api_with_fake_device.py`, đính kèm vào báo cáo cuối.

---

## 9. Thứ tự thực hiện

1. **Chuẩn bị**: liệt kê `frontend/` + `wc -c`; đọc schema/route backend và `docs/api_and_persistence.md`; kiểm tra phiên bản Node; khởi tạo Vite React TS; cài phụ thuộc (ghim phiên bản, `npm ci`); cấu hình Tailwind, ESLint, Vitest, MSW, proxy; cập nhật `.gitignore`; viết `scripts/run_api_with_fake_device.py`. Chạy `lint`, `typecheck`, `test`, `build` (một test mẫu).
2. **Types + API client**: `types/api.ts` (khớp backend thật), `apiClient.ts`, `devicesApi.ts`, `auditsApi.ts`, MSW handlers/fixtures + test mục 7.1.
3. **Xác thực + định tuyến**: `useApiKey`, `ConnectPage`, `AppShell`, route bảo vệ, xử lý 401 + test mục 7.2. **DỪNG LẠI (checkpoint)**: báo cáo cây thư mục, phiên bản các gói đã cài, bảng đối chiếu `types/api.ts` với schema backend (mọi sai khác), và ảnh chụp màn hình kết nối nếu có. Chờ người dùng duyệt.
4. **UI kit + tiện ích**: `Button`, `Badge`, `Modal` (khóa focus), `Spinner`, `EmptyState`, `ErrorBanner`, `Card`, `format.ts`, `strings.ts` + test a11y cơ bản của `Modal`.
5. **Dashboard**: `DevicesPage`, `SummaryTiles`, `DeviceTable`, `AddDeviceDialog`, `DeleteDeviceDialog` + test 7.3–7.4.
6. **Chạy audit**: `RunAuditDialog`, `useRunAudit` + test 7.5 (gồm các kiểm tra bảo mật).
7. **Chi tiết**: `AuditRunPage` (`FindingsTable`, `AuditSummaryHeader`), `DeviceDetailPage` (`AuditHistoryTable`) + test 7.6–7.7.
8. **Hoàn thiện**: responsive, a11y, ESLint jsx-a11y sạch, test 7.8–7.9, `npm run build`, thử toàn bộ luồng với `run_api_with_fake_device.py` (kèm ảnh chụp nếu có thể).
9. **Tài liệu + báo cáo cuối**: `docs/frontend.md` (cách chạy dev qua SSH tunnel, cách build/preview, biến môi trường, cấu trúc thư mục, lưu ý bảo mật: key lưu `sessionStorage`, không bind ra LAN); báo cáo cuối gồm danh sách file, kết quả lint/typecheck/test/build, kết quả `npm audit`, sai khác API, điểm mơ hồ còn lại.

---

## 10. Tiêu chí hoàn thành

- [ ] `npm ci && npm run lint && npm run typecheck && npm test && npm run build` đều xanh.
- [ ] Toàn bộ luồng chạy được với API dev (`run_api_with_fake_device.py`): kết nối → thêm thiết bị → chạy audit (cả hai kiểu credentials) → xem findings → xem lịch sử → xóa thiết bị.
- [ ] Gặp 401 ở bất kỳ trang nào thì đăng xuất và về `/connect`.
- [ ] Không tìm thấy API key, password, enable secret trong URL, `localStorage`, `console`, DOM sau khi đóng hộp thoại, hay mã nguồn (có test tự động).
- [ ] Nội dung từ API không bao giờ được chèn dưới dạng HTML.
- [ ] Run `FAILED` hiển thị rõ mã lỗi và gợi ý tiếng Việt, không có bảng findings.
- [ ] Phụ thuộc được ghim, có lockfile, báo cáo `npm audit`.
- [ ] Không file nào trong `backend/` bị sửa; chỉ thêm `scripts/run_api_with_fake_device.py`.

---

## 11. Để giai đoạn sau (KHÔNG làm ở đây)

- AI giải thích finding (`AIProvider`/Ollama), hiển thị trong hàng findings.
- Snapshot + diff cấu hình, biểu đồ xu hướng điểm bảo mật.
- Remediation có phê duyệt (xem trước lệnh → duyệt → thực thi → xác minh).
- Phục vụ bản build qua reverse proxy có TLS; xác thực người dùng thật; job nền cho audit lâu.
