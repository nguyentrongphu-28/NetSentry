# NetSentry

Nền tảng kiểm toán an ninh cấu hình và khắc phục lỗi tự động cho thiết bị mạng Cisco IOS, tuân thủ chuẩn CIS Benchmark với cơ chế kiểm soát 4 mắt (Four-Eyes Principle) và trợ lý AI an toàn.

---

## 1. Giới Thiệu & Mục Tiêu

NetSentry là giải pháp quản trị an ninh mạng doanh nghiệp, tự động hóa quy trình:
- **Kiểm toán an ninh chuẩn CIS**: Đánh giá 8 quy tắc trọng yếu (NET-001 đến NET-008) cho hệ điều hành Cisco IOS.
- **Quản lý mốc chuẩn & Sai lệch (Baseline & Drift)**: Lưu trữ các bản chụp cấu hình đã che bí mật (HMAC-SHA256) và cảnh báo sai lệch so với mốc chuẩn được phê duyệt.
- **Trợ lý AI giải thích rủi ro an toàn**: Sử dụng mô hình ngôn ngữ lớn (Ollama LLM) cục bộ để giải thích rủi ro kỹ thuật bằng tiếng Việt tự nhiên. AI **chỉ giải thích, tuyệt đối không bao giờ sinh lệnh CLI**, triệt tiêu nguy cơ tấn công Prompt Injection.
- **Khắc phục lỗi có kiểm soát (Safe Remediation)**: Quy trình 4 mắt (Maker-Checker): Operator đề xuất -> Admin độc lập phê duyệt kèm mật khẩu -> Hệ thống áp dụng, xác minh độc lập và tự động hoàn tác (Auto-Rollback) nếu phát hiện lỗi.

---

## 2. Yêu Cầu Hệ Thống & Cài Đặt

### 2.1 Yêu cầu tiên quyết
- **Hệ điều hành**: Linux (Ubuntu 22.04 LTS hoặc tương đương).
- **Python**: Python 3.12 (`python3.12`, `python3.12-venv`).
- **Node.js**: v20.x trở lên và `npm` v10+.
- **Gói mạng bắt buộc (Cố định)**:
  > [!IMPORTANT]
  > Môi trường ảo Python bắt buộc cài đặt chính xác `netmiko==4.8.0` và `paramiko==5.1.0`. Tuyệt đối không nâng cấp hoặc hạ cấp hai gói này để bảo đảm tính tương thích của connectors và allowlist.

### 2.2 Các bước cài đặt
```bash
# 1. Clone kho mã nguồn
git clone https://github.com/your-org/NetSentry.git
cd NetSentry

# 2. Khởi tạo môi trường ảo Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 3. Cài đặt và build giao diện Frontend
cd frontend
npm install
npm run build
cd ..

# 4. Kiểm tra toàn diện môi trường
.venv/bin/python scripts/check_env.py
```

---

## 3. Cấu Hình Biến Môi Trường (Environment Variables)

Sao chép file cấu hình mẫu và điều chỉnh các giá trị phù hợp:
```bash
cp backend/.env.example backend/.env
```

| Tên biến | Kiểu dữ liệu | Mặc định | Mô tả |
| :--- | :---: | :---: | :--- |
| `NETSENTRY_DB_PATH` | string | `netsentry.db` | Đường dẫn tệp cơ sở dữ liệu SQLite |
| `NETSENTRY_API_KEY` | string | (bắt buộc) | Khóa API (tối thiểu 32 ký tự) dùng cho tự động hóa |
| `NETSENTRY_AUTH_DISABLED` | boolean | `0` | Tắt xác thực (Chỉ dùng cho dev nội bộ; cấm trong public mode) |
| `NETSENTRY_PUBLIC_MODE` | boolean | `0` | Chế độ an toàn công khai (tắt `/docs`, chặn truy xuất config thô) |
| `NETSENTRY_ALLOWED_NETWORKS` | string | `""` | Danh sách dải mạng IP CIDR cho phép kết nối router (chống SSRF) |
| `NETSENTRY_ENABLE_DOCS` | boolean | `1` | Bật/tắt tài liệu Swagger UI (`/docs`) |
| `NETSENTRY_SSH_WRITE_USERNAME` | string | `""` | Tên tài khoản SSH có quyền ghi cấu hình router |
| `NETSENTRY_SSH_WRITE_PASSWORD` | string | `""` | Mật khẩu tài khoản SSH có quyền ghi |
| `NETSENTRY_REMEDIATION_EXECUTE_MODE`| string | `live` | Chế độ thực thi: `off`, `dry_run`, `live` |
| `NETSENTRY_AI_ENABLED` | boolean | `1` | Bật/tắt tính năng trợ lý AI giải thích |
| `NETSENTRY_OLLAMA_URL` | string | `http://localhost:11434` | Địa chỉ dịch vụ Ollama cục bộ |
| `NETSENTRY_OLLAMA_MODEL` | string | `qwen2.5:7b` | Tên mô hình LLM sử dụng |

---

## 4. Khởi Chạy Hệ Thống

### 4.1 Khởi tạo dữ liệu người dùng Demo
```bash
.venv/bin/python scripts/seed_demo.py --db backend/netsentry.db
```
Lệnh sẽ tạo 3 tài khoản mặc định: `demo_admin` (Admin), `demo_operator` (Operator), `demo_viewer` (Viewer) kèm mật khẩu ngẫu nhiên hiển thị trên màn hình.

### 4.2 Chạy môi trường Dev với thiết bị giả lập (Không cần phần cứng)
```bash
.venv/bin/python scripts/run_api_with_fake_device.py --fixture insecure --port 8000
```
Truy cập giao diện: `http://localhost:8000` (đăng nhập bằng tài khoản `admin` / `DevAdminPassword123!`).

### 4.3 Chạy API kết nối thiết bị thật phòng Lab
```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --app-dir backend
```

---

## 5. Chạy Kiểm Thử & Đánh Giá Toàn Diện

NetSentry cung cấp script tự động hóa kiểm tra toàn bộ hệ thống từ A đến Z:
```bash
bash scripts/verify_all.sh
```
Quy trình sẽ thực hiện tuần tự:
1. Kiểm tra môi trường hệ thống (`check_env.py`).
2. Đánh giá độ chính xác quy tắc kiểm toán trên tập corpus đóng băng (`rule_eval.py`).
3. Chạy ma trận 15 yêu cầu an ninh S1–S15 (`security_matrix.py`).
4. Đánh giá mức độ kháng tấn công Prompt Injection của AI (`ai_eval.py`).
5. Thực thi bộ kiểm thử backend đầy đủ (Unit, API, E2E Workflows).
6. Kiểm tra tính nhất quán tài liệu và liên kết nội bộ (`check_docs_links.py`).
7. Kiểm tra frontend (Lint, Typecheck, Unit Tests và Build sản phẩm).

---

## 6. Cấu Trúc Thư Mục Dự Án

```
NetSentry/
├── backend/
│   ├── app/
│   │   ├── api/            # Routes, middleware bảo mật, schemas
│   │   ├── connectors/     # SSH Read Connector & Config Writer (Allowlist)
│   │   ├── domain/         # Thực thể nghiệp vụ, lỗi, giao diện
│   │   ├── repositories/   # Tầng lưu trữ cơ sở dữ liệu SQLite
│   │   ├── rules/          # Động cơ phân tích AST cho 8 quy tắc CIS
│   │   ├── security/       # ConfigRedactor (HMAC), PasswordHasher (Argon2id)
│   │   └── services/       # Nghiệp vụ Audit, AI Explain, Remediation
│   └── tests/
│       ├── api/            # Kiểm thử RBAC và API endpoints
│       ├── e2e/            # Kiểm thử kịch bản đầu-cuối tích hợp
│       └── unit/           # Kiểm thử đơn vị logic lõi
├── evaluation/             # Khung đánh giá độ chính xác, an ninh & AI
│   ├── ai/                 # Bộ test case Prompt Injection & Rubric
│   ├── corpus/             # Bộ cấu hình kiểm toán đóng băng & MANIFEST
│   ├── metrics.py          # Thư viện tính ma trận nhầm lẫn & Wilson CI
│   ├── rule_eval.py        # Đánh giá độ chính xác 8 rule CIS
│   └── security_matrix.py  # Chạy ma trận bảo mật S1–S15
├── frontend/               # Giao diện người dùng React 19 + TypeScript
├── docs/                   # Tài liệu kiến trúc, mô hình đe dọa, báo cáo
└── scripts/                # Công cụ hỗ trợ môi trường, seed data, verify
```

---

## 7. Cảnh Báo Đạo Đức & Giới Hạn Trách Nhiệm

> [!CAUTION]
> NetSentry là công cụ an ninh mạng có khả năng can thiệp trực tiếp vào cấu hình thiết bị định tuyến. Chỉ được phép sử dụng hệ thống trên các thiết bị mạng thuộc quyền sở hữu của bạn hoặc đã được sự đồng ý rõ ràng bằng văn bản của đơn vị quản trị. Tuyệt đối không sử dụng công cụ để can thiệp trái phép vào hạ tầng mạng của các tổ chức khác.
