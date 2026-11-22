# Hướng Dẫn Triển Khai Máy Chủ & Khởi Động Công Khai (Server Deployment Guide)

Tài liệu hướng dẫn triển khai NetSentry trên máy chủ kết nối thiết bị mạng Cisco Lab, khởi động an toàn qua Cloudflare Quick Tunnel bằng script `scripts/start_public.sh`.

---

## 1. Cảnh Báo An Ninh Quan Trọng (Security Notice)

> [!CAUTION]
> **Mật khẩu cũ `AdminNetSentry2026!` đã bị lộ trong lịch sử Git (commit 30154f2)**.
> Tuyệt đối **KHÔNG ĐƯỢC** sử dụng lại chuỗi mật khẩu này trên server, database hoặc router lab. Mọi tài khoản admin phải được khởi tạo bằng mật khẩu ngẫu nhiên hoặc nhập an toàn qua `create_admin.py`.

---

## 2. Thiết Lập Biến Môi Trường Bắt Buộc

Trước khi chạy script `scripts/start_public.sh`, bạn bắt buộc phải chỉ định dải mạng của router Cisco để phòng chống tấn công Server-Side Request Forgery (SSRF):

```bash
# Đặt chính xác địa chỉ IP của thiết bị router trong phòng lab (dạng CIDR)
export NETSENTRY_ALLOWED_NETWORKS="192.168.1.1/32"

# (Tùy chọn) Thư mục lưu dữ liệu SQLite và log bên ngoài mã nguồn repo
export NETSENTRY_DATA_DIR="$HOME/netsentry-data"
```

> [!IMPORTANT]
> Script sẽ **từ chối khởi động** nếu biến `NETSENTRY_ALLOWED_NETWORKS` bị bỏ trống, và không chấp nhận các dải mạng mặc định quá rộng (như `10.0.0.0/8` hay `172.16.0.0/12`).

---

## 3. Quản Trị Tài Khoản & Cơ Sở Dữ Liệu

1. **Khởi tạo tài khoản Admin**:
   - Hệ thống không sử dụng bất kỳ mật khẩu mặc định viết sẵn nào.
   - Khi chạy script lần đầu trên terminal tương tác (TTY), script sẽ tự động gọi `backend/scripts/create_admin.py` để bạn nhập mật khẩu an toàn bằng `getpass` (che ký tự, tự động gán cờ `must_change_password=True`).
   - Nếu chạy trong môi trường phi tương tác (cron / CI), hãy khởi tạo admin trước bằng lệnh:
     ```bash
     python backend/scripts/create_admin.py --username admin
     ```
2. **Vị trí lưu trữ cơ sở dữ liệu (`netsentry.db`)**:
   - Mặc định lưu trữ tại `$HOME/netsentry-data/netsentry.db` với quyền thư mục `700` và file log quyền `600`.
   - Cơ sở dữ liệu và file cấu hình `.env` được loại trừ hoàn toàn khỏi Git bởi `.gitignore`.

---

## 4. Chế Độ Công Khai & Quy Tắc Khắc Phục (Public Mode Safeguards)

- **Cố định `NETSENTRY_REMEDIATION_EXECUTE_MODE="off"`**:
  - Khi mở ra Internet qua Cloudflare Quick Tunnel (`NETSENTRY_PUBLIC_MODE=1`), mọi hành động áp dụng thay đổi cấu hình lên router thật **bị vô hiệu hóa tuyệt đối** nhằm ngăn ngừa nguy cơ can thiệp trái phép.
  - API Swagger UI `/docs` và `/openapi.json` bị vô hiệu hóa (trả về mã 404).
  - Mọi route nghiệp vụ đều yêu cầu xác thực phiên đăng nhập (trả về mã 401 nếu chưa login).

### Cách thử nghiệm sửa cấu hình thật (Live Remediation)
Nếu cần thử nghiệm tính năng sửa cấu hình router thật bằng tài khoản admin:
1. **Tuyệt đối không chạy qua Cloudflare Quick Tunnel công khai**.
2. Kết nối trực tiếp vào mạng nội bộ hoặc thiết lập SSH Port Forwarding an toàn:
   ```bash
   ssh -L 8000:127.0.0.1:8000 user@server-ip
   ```
3. Chạy Backend ở chế độ nội bộ với biến môi trường:
   ```bash
   export NETSENTRY_PUBLIC_MODE=0
   export NETSENTRY_REMEDIATION_EXECUTE_MODE=live
   python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
   ```

---

## 5. Khởi Động Bằng Một Lệnh Duy Nhất

Sau khi đã nạp biến `NETSENTRY_ALLOWED_NETWORKS`:
```bash
./scripts/start_public.sh
```

Hệ thống sẽ tự động thẩm định:
- Python 3.12, venv, kiểm tra import `argon2`, `netmiko==4.8.0`, `paramiko==5.1.0`.
- Chờ `/health` phản hồi thành công mới mở Cloudflare Quick Tunnel.
- Thẩm định an ninh endpoints sau khi mở tunnel (`/openapi.json` trả về 404, `/api/v1/devices` trả về 401).
- Khi kết thúc, nhấn `Ctrl+C` để dọn dẹp an toàn cả tiến trình Backend và Cloudflare Tunnel.
