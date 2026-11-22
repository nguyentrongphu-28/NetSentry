# Hướng Dẫn Chi Tiết Vận Hành NetSentry Trên Server & Kết Nối Thiết Bị Thật Cisco Lab

Tài liệu này hướng dẫn chi tiết từng bước cách đưa hệ thống NetSentry lên máy chủ (server/máy lab), cấu hình kết nối thiết bị mạng thật Cisco Router/Switch, thiết lập tài khoản an toàn, và khởi động toàn bộ hệ thống bằng một lệnh duy nhất kết hợp Cloudflare Quick Tunnel để truy cập an toàn từ xa.

---

## 1. Cảnh Báo An Ninh Quan Trọng (Security First)

> [!CAUTION]
> **Mật khẩu cũ `AdminNetSentry2026!` đã bị lộ trong lịch sử Git (commit 30154f2)**.
> Tuyệt đối **KHÔNG ĐƯỢC** sử dụng lại chuỗi mật khẩu này trên server, cơ sở dữ liệu hoặc router lab. Mọi tài khoản admin phải được khởi tạo an toàn bằng mật khẩu ngẫu nhiên hoặc nhập ẩn qua công cụ quản trị.

---

## 2. Chuẩn Bị Môi Trường Trên Server

### 2.1 Yêu cầu hệ thống
- **Hệ điều hành**: Linux (Ubuntu 20.04/22.04/24.04 LTS, Debian, hoặc CentOS/RHEL).
- **Python**: Python 3.12 (`python3.12`, `python3.12-venv`).
- **Node.js**: v20.x trở lên và `npm` v10+.
- **Cloudflared**: Đã cài đặt binary `cloudflared` (nếu muốn mở tunnel truy cập từ xa).
  ```bash
  # Cài đặt cloudflared trên Ubuntu/Debian (nếu chưa có)
  curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
  sudo dpkg -i cloudflared.deb
  rm cloudflared.deb
  cloudflared --version
  ```

### 2.2 Tải mã nguồn và cài đặt dependencies
```bash
# 1. Clone repository về server
git clone <URL_REPO> NetSentry
cd NetSentry

# 2. Khởi tạo môi trường ảo Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Cài đặt các gói phụ thuộc Python (đã bao gồm argon2, netmiko==4.8.0, paramiko==5.1.0)
pip install --upgrade pip
pip install -r backend/requirements.txt

# 4. Cài đặt dependencies và build giao diện Frontend (sản phẩm tĩnh)
cd frontend
npm install
npm run build
cd ..

# 5. Kiểm tra toàn diện điều kiện môi trường
python scripts/check_env.py
```

---

## 3. Cấu Hình Kết Nối Thiết Bị Thật Cisco Lab

### 3.1 Chuẩn bị trên thiết bị Cisco Router
Đảm bảo router Cisco đã được cấu hình IP, SSH và tài khoản truy cập:
```cisco
configure terminal
! 1. Cấu hình hostname và domain
hostname R1-LAB
ip domain-name netsentry.local

! 2. Tạo khóa RSA cho SSH (tối thiểu 2048 bit)
crypto key generate rsa modulus 2048
ip ssh version 2

! 3. Tạo tài khoản cục bộ có đặc quyền (privilege 15)
username netadmin privilege 15 secret YourStrongPasswordHere!

! 4. Bật SSH trên các đường line vty
line vty 0 4
 transport input ssh
 login local
exit

! 5. Bật enable secret
enable secret YourEnableSecretHere!
end
write memory
```

### 3.2 Kiểm tra kết nối từ Server đến Cisco Router
Từ terminal server, xác minh rằng server có thể ping và mở cổng SSH 22 tới router:
```bash
ping -c 3 192.168.1.1
ssh netadmin@192.168.1.1
```

---

## 4. Thiết Lập Biến Môi Trường Bảo Mật

NetSentry tích hợp cơ chế chống SSRF (Server-Side Request Forgery) bắt buộc bạn phải chỉ định IP router hợp lệ thông qua biến `NETSENTRY_ALLOWED_NETWORKS`.

Tạo thư mục dữ liệu bên ngoài mã nguồn để đảm bảo không ghi đè hoặc lộ database vào Git:
```bash
# 1. Tạo thư mục dữ liệu chuyên biệt (phân quyền 700)
mkdir -p "$HOME/netsentry-data"
chmod 700 "$HOME/netsentry-data"

# 2. Thiết lập các biến môi trường cần thiết
export NETSENTRY_DATA_DIR="$HOME/netsentry-data"
export NETSENTRY_DB_PATH="$HOME/netsentry-data/netsentry.db"

# 3. CHỐNG SSRF: Đặt chính xác địa chỉ IP của Cisco router (bắt buộc, dạng CIDR /32)
export NETSENTRY_ALLOWED_NETWORKS="192.168.1.1/32"

# 4. Khóa API bí mật của hệ thống (tối thiểu 32 ký tự ngẫu nhiên)
export NETSENTRY_API_KEY="$(openssl rand -hex 32)"
```

---

## 5. Khởi Tạo Tài Khoản Quản Trị Viên (Admin Account)

NetSentry **không có mật khẩu mặc định**. Lần đầu triển khai, bạn cần tạo tài khoản Admin bằng công cụ an toàn (nhập bằng `getpass`, tự động băm Argon2id và yêu cầu đổi mật khẩu ở lần đăng nhập đầu tiên):

```bash
source .venv/bin/activate
python backend/scripts/create_admin.py --username admin
```
Hệ thống sẽ nhắc bạn:
```text
Enter password for admin: [nhập mật khẩu bí mật]
Confirm password: [nhập lại mật khẩu]
Admin user 'admin' created successfully.
```

---

## 6. Khởi Động Bằng Một File Duy Nhất (`scripts/start_public.sh`)

Để tối ưu hóa quá trình vận hành, NetSentry cung cấp script tự động hóa toàn bộ quy trình:
1. Kiểm tra Python venv và phiên bản cố định `netmiko==4.8.0`, `paramiko==5.1.0`.
2. Kiểm tra biến môi trường chống SSRF.
3. Khởi chạy Backend FastAPI (phục vụ cả API và Frontend SPA tĩnh) ở chế độ an toàn công khai (`NETSENTRY_PUBLIC_MODE=1`, `NETSENTRY_REMEDIATION_EXECUTE_MODE="off"`).
4. Kiểm tra sức khỏe `/health` cho đến khi backend phản hồi `healthy`.
5. Tự động bật Cloudflare Quick Tunnel và lấy đường link public HTTPS.
6. Xác thực bảo mật post-tunnel (`/openapi.json` trả về 404, `/api/v1/devices` yêu cầu xác thực 401).

### 6.1 Lệnh khởi động
```bash
./scripts/start_public.sh
```

### 6.2 Kết quả trên màn hình
```text
[OK] Sử dụng môi trường ảo: /home/user/NetSentry/.venv
[OK] Thư viện argon2, netmiko (4.8.0), paramiko (5.1.0) đã sẵn sàng.
[OK] Thư mục dữ liệu: /home/user/netsentry-data
[OK] Cơ sở dữ liệu: /home/user/netsentry-data/netsentry.db
[OK] NETSENTRY_ALLOWED_NETWORKS: 192.168.1.1/32
[OK] Đã tìm thấy tài khoản admin trong hệ thống.
[*] Khởi chạy backend uvicorn ở chế độ nền...
[*] Đang chờ Backend khởi động (tối đa 30s)...
[OK] Backend đã phản hồi sẵn sàng tại http://127.0.0.1:8000/health!
[*] Khởi chạy Cloudflare Quick Tunnel...
[OK] Đã kết nối Cloudflare Tunnel!
======================================================================
  ĐƯỜNG DẪN TRUY CẬP CÔNG KHAI (CLOUDFLARE TUNNEL):
  https://random-subdomain.trycloudflare.com
======================================================================
[OK] Thẩm định an ninh: OpenAPI/Docs đã bị ẩn (404 Not Found).
[OK] Thẩm định an ninh: API nghiệp vụ yêu cầu xác thực (401 Unauthorized).
[!] Nhấn Ctrl+C để dừng toàn bộ hệ thống (Backend & Cloudflare Tunnel).
```

Chỉ cần mở đường dẫn `https://random-subdomain.trycloudflare.com` trên trình duyệt máy tính cá nhân hoặc điện thoại là có thể đăng nhập vào giao diện NetSentry.

---

## 7. Các Thao Tác Nghiệp Vụ Trên Giao Diện

### 7.1 Đăng nhập và Đổi mật khẩu
1. Mở link Cloudflare Tunnel.
2. Đăng nhập bằng `admin` và mật khẩu vừa khởi tạo ở Bước 5.
3. Vì cờ `must_change_password=True`, giao diện sẽ ngay lập tức yêu cầu bạn đặt mật khẩu mới trước khi tiếp tục.

### 7.2 Thêm thiết bị Cisco Router vào danh sách giám sát
1. Vào menu **Devices** -> bấm **Add Device**.
2. Điền thông tin kết nối:
   - **Hostname**: `R1-LAB`
   - **Management IP**: `192.168.1.1` (phải nằm trong dải `NETSENTRY_ALLOWED_NETWORKS` đã cấu hình).
   - **Platform**: `cisco_ios`
   - **SSH Port**: `22`
   - **Username**: `netadmin`
   - **Password**: Nhập mật khẩu SSH của router.
   - **Secret**: Nhập enable secret của router.
3. Bấm **Save**. Hệ thống sẽ mã hóa an toàn credentials trong database.

### 7.3 Thực hiện kiểm toán an ninh (Run Audit)
1. Tại danh sách thiết bị, chọn router `R1-LAB` -> bấm **Run Audit**.
2. Hệ thống SSH vào router, thu thập running-config, áp dụng bộ lọc che bí mật (HMAC Config Redactor), và đánh giá 8 quy tắc CIS:
   - `NET-001`: AAA Authentication
   - `NET-002`: Password Encryption Service
   - `NET-003`: SSH Configuration & Version 2
   - `NET-004`: Login Banner Cảnh báo
   - `NET-005`: VTY Access-List & Timeout
   - `NET-006`: Vô hiệu hóa HTTP Server không an toàn
   - `NET-007`: Cấu hình SNMP an toàn
   - `NET-008`: Thiết lập Logging & Syslog
3. Bấm vào chi tiết Audit để xem kết quả Pass/Fail và sử dụng nút **Explain with AI** để xem giải thích rủi ro bằng tiếng Việt tự nhiên.

---

## 8. Thử Nghiệm Sửa Cấu Hình Thật (Live Remediation)

> [!IMPORTANT]
> Khi chạy qua Cloudflare Quick Tunnel (`start_public.sh`), hệ thống **cố định `NETSENTRY_REMEDIATION_EXECUTE_MODE="off"`** để đảm bảo tuyệt đối không ai trên Internet có thể kích hoạt lệnh thay đổi cấu hình router.

Nếu bạn muốn thử nghiệm tính năng áp dụng cấu hình tự động (Live Remediation) lên router phòng Lab:
1. **Dừng Cloudflare Tunnel** (nhấn `Ctrl+C`).
2. **Sử dụng SSH Local Port Forwarding** để truy cập nội bộ an toàn:
   ```bash
   # Từ máy tính của bạn mở cổng forward tới server:
   ssh -L 8000:127.0.0.1:8000 user@server-ip
   ```
3. **Khởi chạy Backend ở chế độ nội bộ (Local Mode)**:
   ```bash
   source .venv/bin/activate
   export NETSENTRY_PUBLIC_MODE=0
   export NETSENTRY_REMEDIATION_EXECUTE_MODE=live
   export NETSENTRY_ALLOWED_NETWORKS="192.168.1.1/32"
   python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --app-dir backend
   ```
4. Truy cập `http://localhost:8000`:
   - Operator đề xuất phương án khắc phục (Remediation Plan).
   - Admin kiểm tra diff, phê duyệt bằng mật khẩu (Four-Eyes Principle).
   - Hệ thống tự động đẩy lệnh cấu hình qua SSH allowlist, kiểm tra lại trạng thái và tự động rollback nếu phát hiện sai sót.

---

## 9. Xử Lý Sự Cố Thường Gặp (Troubleshooting)

| Hiện tượng | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| `[LỖI] Biến môi trường NETSENTRY_ALLOWED_NETWORKS chưa được đặt!` | Chưa chỉ định IP router | Chạy `export NETSENTRY_ALLOWED_NETWORKS="IP/32"` trước khi chạy script. |
| `[LỖI] Thiếu thư viện Python: argon2` | Chưa cài đủ dependencies | Kích hoạt `.venv` và chạy `pip install -r backend/requirements.txt`. |
| `Backend không phản hồi sau 30s!` | Lỗi cấu hình hoặc cổng 8000 đang bị chiếm | Xem file log tại `$NETSENTRY_DATA_DIR/backend.log` để biết chi tiết lỗi. |
| Router từ chối kết nối SSH | Sai username/password hoặc chưa bật SSH v2 | Kiểm tra `ssh user@router_ip` từ terminal server; kiểm tra `crypto key generate rsa` trên router. |
| Thêm thiết bị báo lỗi IP không được phép | IP router vi phạm SSRF allowlist | Đảm bảo IP router nằm trong dải `NETSENTRY_ALLOWED_NETWORKS`. |
