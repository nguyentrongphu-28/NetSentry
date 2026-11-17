# NetSentry – REST API & Persistence Documentation

Tài liệu hướng dẫn sử dụng và vận hành module Lưu trữ (SQLite) và Giao diện lập trình REST API (FastAPI) của NetSentry.

---

## 1. Khởi chạy Dịch vụ API

NetSentry sử dụng mô hình Application Factory (`create_app`) nhằm tối ưu hoá cấu hình môi trường và kiểm thử độc lập. Không khởi tạo ứng dụng trực tiếp ở cấp module.

### Lệnh chạy với Uvicorn:
Từ thư mục gốc dự án:
```bash
# Thiết lập biến môi trường bắt buộc (API Key tối thiểu 16 ký tự)
export NETSENTRY_API_KEY="my-very-strong-api-key-at-least-16-chars"

# Khởi chạy máy chủ API qua uvicorn factory
uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000
```

Hoặc chuyển trực tiếp vào thư mục `backend/`:
```bash
cd backend
export NETSENTRY_API_KEY="my-very-strong-api-key-at-least-16-chars"
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

> **Lưu ý về Virtual Environment:**
> Dự án sử dụng môi trường Python đặc biệt (phiên bản `paramiko==5.1.0` và `netmiko==4.8.0`) tương thích với các dòng Cisco router trong phòng lab. Tuyệt đối không tự ý nâng/hạ phiên bản của hai thư viện này khi cài đặt thêm các gói khác. Luôn kích hoạt môi trường ảo trước khi chạy:
> ```bash
> source .venv/bin/activate
> ```

---

## 2. Truy cập từ xa an toàn qua SSH Tunnel

Để bảo đảm an toàn, máy chủ API chỉ nên bind vào địa chỉ loopback cục bộ (`127.0.0.1`). Để tương tác hoặc gọi API từ máy trạm của quản trị viên qua mạng:

```bash
# Chuyển tiếp cổng 8000 từ server về máy trạm cá nhân qua SSH Tunnel
ssh -L 8000:127.0.0.1:8000 user@server-ip
```

Sau khi mở tunnel, bạn có thể gửi request đến `http://127.0.0.1:8000` trên máy trạm mà toàn bộ dữ liệu (kể cả API Key và thông tin xác thực) đều được mã hóa trong đường hầm SSH.

---

## 3. Bảng biến môi trường

| Biến môi trường | Mặc định | Bắt buộc | Mô tả |
|---|---|---|---|
| `NETSENTRY_API_KEY` | – | Có* | Khóa xác thực API, tối thiểu 16 ký tự (*trừ khi tắt auth). |
| `NETSENTRY_AUTH_DISABLED` | `0` | Không | Đặt `1` để tắt xác thực API (chỉ dùng khi dev, sẽ in cảnh báo). |
| `NETSENTRY_DB_PATH` | `<repo>/data/netsentry.db` | Không | Đường dẫn tới file cơ sở dữ liệu SQLite. |
| `NETSENTRY_CORS_ORIGINS` | rỗng | Không | Danh sách domain được phép gọi API (phân tách bởi dấu phẩy). |
| `NETSENTRY_ALLOWED_NETWORKS` | rỗng | Không | Danh sách CIDR cho phép thêm thiết bị (phòng chống SSRF). |
| `NETSENTRY_ENABLE_DOCS` | `1` | Không | Bật (`1`) hoặc tắt (`0`) các trang `/docs`, `/redoc`, `/openapi.json`. |
| `NETSENTRY_SSH_USERNAME` | – | Không | Tên tài khoản SSH dự phòng dùng khi request audit không gửi kèm credentials. |
| `NETSENTRY_SSH_PASSWORD` | – | Không | Mật khẩu SSH dự phòng. |
| `NETSENTRY_ENABLE_SECRET` | – | Không | Mật khẩu enable secret dự phòng cho Cisco IOS. |

---

## 4. Danh sách API Endpoints (`/api/v1`)

Mọi endpoint (ngoại trừ `GET /health`) đều yêu cầu header xác thực `X-API-Key: <your-key>`.

| Phương thức | Đường dẫn | Mô tả | Mã thành công | Mã lỗi |
|---|---|---|---|---|
| `GET` | `/health` | Kiểm tra tình trạng dịch vụ (không cần API key) | `200 OK` | – |
| `POST` | `/api/v1/devices` | Đăng ký thiết bị mới | `201 Created` | `401`, `409`, `422` |
| `GET` | `/api/v1/devices` | Danh sách thiết bị + tóm tắt audit gần nhất | `200 OK` | `401` |
| `GET` | `/api/v1/devices/{device_id}` | Xem chi tiết thiết bị + tóm tắt audit gần nhất | `200 OK` | `401`, `404` |
| `DELETE` | `/api/v1/devices/{device_id}` | Xóa thiết bị và toàn bộ lịch sử audit (cascade) | `204 No Content` | `401`, `404` |
| `POST` | `/api/v1/devices/{device_id}/audit` | Kích hoạt chạy audit trên thiết bị | `201 Created` | `401`, `404`, `409`, `422` |
| `GET` | `/api/v1/devices/{device_id}/audits` | Lịch sử các lần audit của thiết bị (phân trang) | `200 OK` | `401`, `404` |
| `GET` | `/api/v1/audits/{run_id}` | Xem chi tiết 1 lần audit và toàn bộ findings | `200 OK` | `401`, `404` |
| `GET` | `/api/v1/audits/{run_id}/findings` | Lọc các findings theo trạng thái và mức độ nghiêm trọng | `200 OK` | `401`, `404`, `422` |

---

## 5. Ví dụ cURL đầy đủ

### 5.1 Kiểm tra Health Check
```bash
curl -s http://127.0.0.1:8000/health
```
*Phản hồi:*
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### 5.2 Đăng ký thiết bị mới
```bash
curl -X POST http://127.0.0.1:8000/api/v1/devices \
  -H "X-API-Key: my-very-strong-api-key-at-least-16-chars" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "Router-Core-01",
    "name": "Core Router Khu vực 1",
    "host": "192.168.1.1",
    "port": 22,
    "platform": "cisco_ios"
  }'
```
*Phản hồi (`201 Created`):*
```json
{
  "device_id": "Router-Core-01",
  "name": "Core Router Khu vực 1",
  "host": "192.168.1.1",
  "port": 22,
  "platform": "cisco_ios",
  "created_at": "2026-11-17T06:00:00+00:00",
  "updated_at": "2026-11-17T06:00:00+00:00"
}
```

### 5.3 Chạy Audit với Credentials truyền trong Body
```bash
curl -X POST http://127.0.0.1:8000/api/v1/devices/Router-Core-01/audit \
  -H "X-API-Key: my-very-strong-api-key-at-least-16-chars" \
  -H "Content-Type: application/json" \
  -d '{
    "credentials": {
      "username": "cisco_admin",
      "password": "MySecretPassword123!",
      "enable_secret": "MyEnableSecret456!"
    }
  }'
```

### 5.4 Chạy Audit dùng Credentials dự phòng từ biến môi trường
Nếu server đã được cấu hình các biến `NETSENTRY_SSH_USERNAME`, `NETSENTRY_SSH_PASSWORD`, client chỉ cần gửi body rỗng `{}`:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/devices/Router-Core-01/audit \
  -H "X-API-Key: my-very-strong-api-key-at-least-16-chars" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 5.5 Xem kết quả chi tiết của Run và Lọc Findings
Lấy chi tiết lượt audit:
```bash
curl -X GET http://127.0.0.1:8000/api/v1/audits/1 \
  -H "X-API-Key: my-very-strong-api-key-at-least-16-chars"
```

Lọc các lỗi có trạng thái `FAIL` và mức độ nghiêm trọng `HIGH`:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/audits/1/findings?status=FAIL&severity=HIGH" \
  -H "X-API-Key: my-very-strong-api-key-at-least-16-chars"
```

### 5.6 Xóa thiết bị
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/devices/Router-Core-01 \
  -H "X-API-Key: my-very-strong-api-key-at-least-16-chars"
```
*Phản hồi:* `204 No Content` (thiết bị và toàn bộ audit history liên quan sẽ tự động bị xóa theo cơ chế CASCADE).

---

## 6. Cảnh báo và Thực hành Bảo mật

1. **Không lưu trữ Credentials trong Cơ sở dữ liệu**:
   - Database SQLite tuyệt đối không có bảng, cột hay trường dữ liệu nào lưu mật khẩu thiết bị hoặc raw configuration.
   - Credentials chỉ tồn tại trong bộ nhớ ngắn hạn của phiên kết nối SSH và được giải phóng ngay sau khi thu thập config xong.
2. **Bảo vệ Credentials truyền trong Body**:
   - Khi truyền credentials qua REST API, chỉ giao tiếp qua mạng nội bộ bảo mật, HTTPS (đặt sau TLS reverse proxy như Nginx/Caddy) hoặc qua SSH Tunnel.
3. **Phòng chống SSRF (Server-Side Request Forgery)**:
   - Trong môi trường production, luôn thiết lập biến môi trường `NETSENTRY_ALLOWED_NETWORKS` (ví dụ: `192.168.1.0/24,10.0.0.0/16`) để chỉ cho phép kết nối đến các dải mạng quản trị thiết bị xác định trước, ngăn chặn hacker lợi dụng API để quét các máy chủ nội bộ khác.
4. **Không rò rỉ dữ liệu nhạy cảm qua lỗi Validation**:
   - Trình xử lý ngoại lệ `RequestValidationError` của NetSentry đã loại bỏ hoàn toàn trường `input` mặc định của FastAPI, đảm bảo nếu người dùng gửi sai cấu trúc kèm mật khẩu, mật khẩu đó không bao giờ bị phản hồi ngược lại trong mã lỗi 422.
