# NetSentry – Tài liệu Frontend Dashboard

> **Ngôn ngữ giao diện:** Tiếng Việt · **Ngôn ngữ code/biến/comment:** Tiếng Anh

---

## 1. Yêu cầu môi trường

| Thứ | Phiên bản |
|---|---|
| Node.js | >= 20.0.0 (LTS) · môi trường dev đang dùng **v24.15.0** |
| npm | đi kèm Node; dùng `npm ci` để cài (không dùng `npm install` trong CI) |
| Python | >= 3.10 (chỉ cần cho server giả lập, mục 4) |

---

## 2. Cài đặt

```bash
cd frontend
npm ci          # cài đúng phiên bản trong package-lock.json
```

---

## 3. Chạy môi trường dev

### 3.1 Cấu trúc proxy

API backend chạy tại `127.0.0.1:8000` và **chỉ bind localhost** — không có CORS.  
Frontend dùng **proxy của Vite** để chuyển mọi request `/api/...` và `/health` sang backend:

```
Trình duyệt → http://localhost:5173/api/v1/...
                        │
                 Vite dev server (proxy)
                        │
              http://127.0.0.1:8000/api/v1/...
```

Biến môi trường `VITE_API_PROXY_TARGET` (mặc định `http://127.0.0.1:8000`) điều chỉnh đích proxy. Xem `.env.example`:

```dotenv
# frontend/.env.example
# KHÔNG đặt API key hoặc secret vào bất kỳ biến VITE_* nào!
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

### 3.2 Kịch bản dev trực tiếp (backend chạy cùng máy)

```bash
# Terminal 1 – backend (hoặc server giả lập, xem mục 4)
cd /path/to/NetSentrySelf
.venv/bin/python scripts/run_api_with_fake_device.py --api-key <key>

# Terminal 2 – frontend dev server
cd frontend
npm run dev
# → http://127.0.0.1:5173
```

### 3.3 Kịch bản dev qua SSH tunnel (backend ở server từ xa)

Backend chỉ bind `127.0.0.1` nên cần tunnel:

```bash
# Máy dev – mở tunnel (giữ nguyên trong suốt phiên làm việc)
ssh -L 8000:127.0.0.1:8000 user@your-server

# Máy dev – chạy frontend (không cần Node trên server)
cd frontend
npm run dev
# Trình duyệt vào http://localhost:5173
```

> [!IMPORTANT]
> Không bao giờ bind Vite dev server lên `0.0.0.0` hay IP công khai — file `vite.config.ts` đã cố định `host: "127.0.0.1"`.

---

## 4. Dev với thiết bị giả lập (`run_api_with_fake_device.py`)

Script `scripts/run_api_with_fake_device.py` khởi động toàn bộ backend NetSentry với `FakeConnector` thay cho SSH thật — **chỉ dùng trong dev, không dùng production**.

```bash
.venv/bin/python scripts/run_api_with_fake_device.py [OPTIONS]
```

| Tùy chọn | Mô tả | Mặc định |
|---|---|---|
| `--fixture {insecure,secure,minimal,banner_trap}` | Bộ cấu hình giả lập | `insecure` |
| `--fail-on {auth,timeout,connect,collection}` | Giả lập lỗi kết nối để thử giao diện run FAILED | _(không lỗi)_ |
| `--api-key KEY` | API key tùy chỉnh (tối thiểu 16 ký tự) | _(random 32 ký tự)_ |
| `--port PORT` | Cổng lắng nghe | `8000` |
| `--host HOST` | Host bind | `127.0.0.1` |

**Ví dụ:**

```bash
# Chạy với fixture "banner_trap" (tự sinh ngẫu nhiên API key và in ra terminal)
.venv/bin/python scripts/run_api_with_fake_device.py \
    --fixture banner_trap

# Giả lập lỗi xác thực SSH thiết bị để thử giao diện run FAILED
.venv/bin/python scripts/run_api_with_fake_device.py \
    --fail-on auth

# Giả lập timeout kết nối thiết bị
.venv/bin/python scripts/run_api_with_fake_device.py \
    --fail-on timeout
```

Ánh xạ `--fail-on` → exception backend:

| Giá trị | Exception |
|---|---|
| `auth` | `AuthenticationFailedError` |
| `timeout` | `ConnectionTimeoutError` |
| `connect` | `ConnectionFailedError` |
| `collection` | `ConfigCollectionError` |

---

## 5. Build & Preview

```bash
# Build production (tsc + vite build)
cd frontend
npm run build
# → dist/

# Preview bản build (cũng dùng proxy, xem vite.config.ts)
npm run preview
# → http://127.0.0.1:5173
```

> [!NOTE]
> `npm run preview` cũng dùng `preview.proxy` trong `vite.config.ts` nên hoạt động giống dev — backend vẫn phải đang chạy ở `VITE_API_PROXY_TARGET`.

---

## 6. Lint, Typecheck, Test

```bash
cd frontend
npm run lint        # ESLint (TypeScript + React Hooks + jsx-a11y)
npm run typecheck   # tsc --noEmit (strict mode)
npm test            # Vitest run (tất cả file *.test.ts/tsx)
```

> [!TIP]
> Chạy theo thứ tự trên để phát hiện lỗi từ sớm. Tất cả ba lệnh phải xanh trước khi commit.

### Tóm tắt kết quả kiểm thử tự động (lần chạy gần nhất)

```
Test Files  11 passed (11)
     Tests  57 passed (57)
  Start at  15:01:44
  Duration  58.64s
```

---

## 7. Cấu trúc thư mục

```
frontend/
├── index.html
├── package.json            # phụ thuộc ghim phiên bản chính xác (không ^ ~)
├── package-lock.json
├── tsconfig.json           # strict: true
├── vite.config.ts          # proxy /api và /health → VITE_API_PROXY_TARGET
├── vitest.config.ts
├── eslint.config.js        # TypeScript + react-hooks + jsx-a11y
├── postcss.config.js
├── tailwind.config.js
├── .env.example
└── src/
    ├── main.tsx
    ├── App.tsx             # Router + QueryClient + ApiKeyProvider
    ├── index.css           # Tailwind directives
    ├── types/
    │   └── api.ts          # TypeScript types từ backend schemas
    ├── i18n/
    │   └── strings.ts      # Toàn bộ chuỗi tiếng Việt hiển thị trên UI
    ├── services/
    │   ├── apiClient.ts    # fetch wrapper: X-API-Key header, timeout, parse lỗi, 401
    │   ├── devicesApi.ts
    │   └── auditsApi.ts
    ├── hooks/
    │   ├── useApiKey.tsx   # Context + sessionStorage (key: "netsentry.apiKey")
    │   ├── useDevices.ts
    │   ├── useDevice.ts
    │   ├── useAuditRuns.ts
    │   ├── useAuditRun.ts
    │   ├── useRunAudit.ts
    │   ├── useCreateDevice.ts
    │   └── useDeleteDevice.ts
    ├── utils/
    │   └── format.ts       # Định dạng thời gian, thứ tự severity/status
    ├── components/
    │   ├── ui/             # Button, Badge, Modal, Spinner, EmptyState, ErrorBanner, Card
    │   ├── layout/         # AppShell (nav + logout)
    │   ├── devices/        # DeviceTable, SummaryTiles, AddDeviceDialog,
    │   │                   # DeleteDeviceDialog, RunAuditDialog
    │   └── audits/         # AuditHistoryTable, FindingsTable, FindingRow,
    │                       # StatusBadge, SeverityBadge, AuditSummaryHeader
    ├── pages/
    │   ├── ConnectPage.tsx
    │   ├── DevicesPage.tsx
    │   ├── DeviceDetailPage.tsx
    │   ├── AuditRunPage.tsx
    │   └── NotFoundPage.tsx
    └── test/
        ├── setup.ts            # @testing-library/jest-dom matchers, MSW lifecycle
        ├── fixtures.ts         # Dữ liệu mẫu dùng chung cho tests
        ├── msw/
        │   ├── handlers.ts     # MSW request handlers
        │   └── server.ts       # MSW server (setupServer)
        ├── smoke.test.tsx
        ├── auth_routing.test.tsx
        └── security_a11y.test.tsx
```

---

## 8. Bảng mục đặc tả → tên test

### Mục 7.3 & 7.4 – Dashboard thiết bị (`DevicesPage.test.tsx`, 8 tests)

| Mục đặc tả | Tên test |
|---|---|
| 7.3 Thẻ tổng hợp tính đúng từ danh sách mẫu | `calculates and displays summary tiles correctly from sample devices` |
| 7.3 Trạng thái rỗng khi không có thiết bị | `displays empty state when device list is empty` |
| 7.3 Banner lỗi + nút retry khi API thất bại | `displays error banner with retry button on API failure` |
| 7.4 Validate trường client + tạo thiết bị thành công | `validates client fields and creates new device successfully` |
| 7.4 Lỗi 409 DEVICE_EXISTS hiển thị bên cạnh trường device_id | `displays server error 409 DEVICE_EXISTS next to device_id field` |
| 7.3 Spinner loading khi đang tải | `displays loading spinner while fetching devices` |
| 7.4 Lỗi 422 VALIDATION_ERROR hiển thị theo từng trường | `displays server error 422 VALIDATION_ERROR next to fields` |
| 7.4 Mở hộp thoại xóa và xóa thiết bị thành công | `opens delete dialog and deletes device successfully` |

### Mục 7.5 – Chạy audit (`RunAuditDialog.test.tsx`, 11 tests)

| Mục đặc tả | Tên test |
|---|---|
| 7.5 Bắt buộc nhập username/password | `requires username and password fields on submit` |
| 7.5 Gửi credentials thủ công → điều hướng khi 201 COMPLETED | `submits manual credentials and navigates to audit detail on 201 COMPLETED` |
| 7.5 Điều hướng khi 201 FAILED | `navigates to audit detail on 201 FAILED run as well` |
| 7.5 Bấm đúp → đúng 1 request (double-click) | `prevents double submission: counts MSW handler calls and asserts exactly 1 on double-click` |
| 7.5 Nhấn Enter hai lần → đúng 1 request | `prevents double submission: pressing Enter twice only triggers exactly 1 API call` |
| 7.5 Đóng hộp thoại giữa chừng → KHÔNG tự điều hướng | `does not navigate when dialog is closed before audit completes, triggers background callback` |
| 7.5 Lỗi 409 AUDIT_ALREADY_RUNNING | `displays server error 409 AUDIT_ALREADY_RUNNING` |
| 7.5 Lỗi 404 DEVICE_NOT_FOUND | `displays server error 404 DEVICE_NOT_FOUND` |
| 7.5 Lỗi 422 VALIDATION_ERROR hiển thị theo trường | `displays 422 VALIDATION_ERROR with field errors from details attached to inputs` |
| 7.5 Mã CLIENT_TIMEOUT → hiển thị `timeoutNotice` | `displays notice when client timeout occurs (CLIENT_TIMEOUT)` |
| 7.5 Bảo mật: password không rò rỉ ra DOM/storage/console | `security test: secret FAKE-UI-PW never leaks to console, storage, or DOM after close` |

### Mục 7.6 – Trang chi tiết lần audit (`AuditRunPage.test.tsx`, 5 tests)

| Mục đặc tả | Tên test |
|---|---|
| 7.6 Thứ tự sắp xếp mặc định FAIL > UNKNOWN > PASS | `renders audit summary header and findings in default sort order (FAIL > UNKNOWN > PASS)` |
| 7.6 Lọc theo status và severity | `filters findings by status and severity correctly` |
| 7.6 Mở rộng hàng, aria-expanded, sao chép remediation | `expands a finding row, verifies aria-expanded and copies remediation text` |
| 7.6 XSS: `<script>`, `<img onerror>` bị escape thành text | `prevents XSS: raw HTML or scripts in findings are escaped and rendered as text` |
| 7.6 Run FAILED → khối lỗi nổi bật, KHÔNG hiện bảng findings | `displays prominent error block and NO findings table when run is FAILED` |

### Mục 7.7 – Trang chi tiết thiết bị (`DeviceDetailPage.test.tsx`, 3 tests)

| Mục đặc tả | Tên test |
|---|---|
| 7.7 Hiển thị thông tin thiết bị và audit gần nhất | `renders device details and latest audit summary correctly` |
| 7.7 Phân trang lịch sử limit/offset/total + điều hướng biên | `displays paginated audit history with limit, offset, total and boundary controls` |
| 7.7 Trạng thái rỗng khi chưa có lịch sử | `renders empty state when device has no previous audit history` |

### Mục 7.8 & 7.9 – Bảo mật & trợ năng (`security_a11y.test.tsx`, 4 tests)

| Mục đặc tả | Tên test |
|---|---|
| 7.8 Không dùng `dangerouslySetInnerHTML` trong source | `never uses dangerouslySetInnerHTML in application source code (Section 7.8)` |
| 7.9 Không dùng `localStorage` trong source | `never uses localStorage in application source code (Section 7.9)` |
| 7.9 Không lộ API key qua `VITE_*KEY` | `never exposes API keys in VITE_ environment variables or source files (Section 7.9)` |
| 7.8 StatusBadge và SeverityBadge luôn render text hiển thị | `StatusBadge and SeverityBadge always render visible text for accessibility (Section 7.8)` |

### Các bài kiểm thử khác

| File | Số lượng | Phạm vi |
|---|---|---|
| `FindingRow.test.tsx` | 3 | Sao chép clipboard: thành công, Promise bị từ chối, `navigator.clipboard` không tồn tại |
| `auth_routing.test.tsx` | 6 | Redirect khi chưa có key, bảo toàn khi có key, nút đăng xuất |
| `Modal.test.tsx` | 4 | Render, đóng bằng Escape/overlay/nút, focus trap |
| `apiClient.test.ts` | 6 | Timeout 15 s, gửi `X-API-Key`, parse lỗi có cấu trúc, lỗi mạng, 401 |
| `format.test.ts` | 6 | Định dạng ngày giờ, thứ tự severity, thứ tự status |
| `smoke.test.tsx` | 1 | App render không crash |

---

## 9. Biến môi trường

| Biến | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|
| `VITE_API_PROXY_TARGET` | Không | `http://127.0.0.1:8000` | Địa chỉ backend để proxy |

> [!CAUTION]
> **Không bao giờ** đặt API key, password, hay secret vào biến `VITE_*` — chúng được nhúng vào bundle JavaScript và công khai với mọi trình duyệt. API key được nhập trực tiếp bởi người dùng trên màn hình kết nối.

---

## 10. Ghi chú bảo mật

| Điểm | Triển khai |
|---|---|
| **Lưu API key** | Chỉ `sessionStorage` (key `netsentry.apiKey`); tự mất khi đóng tab |
| **Không localStorage** | Kiểm tra tĩnh trong `security_a11y.test.tsx` |
| **XSS** | Không dùng `dangerouslySetInnerHTML`; React tự escape; kiểm tra tĩnh + test DOM |
| **Clipboard** | `navigator.clipboard.writeText()` async; không dùng `document.execCommand` |
| **Bind dev server** | `host: "127.0.0.1"` trong `vite.config.ts` — không expose LAN |
| **Không API key trong VITE_*** | Kiểm tra tĩnh trong `security_a11y.test.tsx` |
| **Thời gian chờ** | 15 s cho request thường; 120 s cho `POST /devices/{id}/audit` (dùng `AbortController`) |

---

## 11. npm audit

```bash
cd frontend
npm audit
```

> [!NOTE]
> Lệnh này cần **kết nối mạng tới registry.npmjs.org**. Không thể chạy trong môi trường sandbox/offline.  
> Package `minimatch` đã được override lên `11.0.1` trong `package.json` để vá lỗ hổng đã biết.  
> Chạy `npm audit` định kỳ trong môi trường có mạng (CI/CD pipeline) trước khi deploy.

---

## 12. Phần đã kiểm thử tự động / cần kiểm thử tay

### ✅ Đã kiểm thử tự động (Vitest + MSW)

- Tất cả các luồng API (thành công, lỗi có cấu trúc, timeout, lỗi mạng)
- Điều hướng sau khi đăng nhập/đăng xuất
- Validate form client-side và server-side
- Ngăn submit đúp (double-click và Enter×2)
- Hành vi đóng hộp thoại giữa chừng
- Sắp xếp, lọc findings
- Mở rộng hàng và aria-expanded
- Sao chép remediation (thành công, từ chối, thiếu API)
- Phân trang lịch sử
- XSS escape
- Kiểm tra tĩnh: `dangerouslySetInnerHTML`, `localStorage`, `VITE_*KEY`
- Trợ năng badges

### 🖐️ Cần kiểm thử tay trên trình duyệt thật

- Luồng đầy đủ với `run_api_with_fake_device.py` (các fixture và `--fail-on`)
- Hiển thị responsive trên màn hình nhỏ
- Trình đọc màn hình (screen reader) với các vùng `role="status"` / `role="alert"`
- Scroll behavior của bảng findings khi nhiều dòng
- Hiển thị cross-browser (Chrome, Firefox, Safari)
- `npm audit` (yêu cầu mạng)

---

## 13. Các sai khác phát hiện so với đặc tả

Không phát hiện sai khác giữa đặc tả `docs/frontend_spec.md` và code backend thật trong quá trình triển khai. Mọi type trong `src/types/api.ts` đều được đọc từ `backend/app/api/schemas/*.py` và `backend/app/api/routes/*.py`.
