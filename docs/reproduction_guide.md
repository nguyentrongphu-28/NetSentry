# Hướng Dẫn Tái Lập Môi Trường (Reproduction Guide)

Tài liệu hướng dẫn chi tiết từng bước tái lập hệ thống NetSentry trên một máy tính sạch (Clean Machine) chạy hệ điều hành Linux (Ubuntu/Debian), từ clone repo đến chạy demo hoàn chỉnh, kèm bảng xử lý sự cố thường gặp.

---

## 1. Yêu Cầu Tiền Đề Hệ Thống (Prerequisites)

- **Hệ điều hành**: Linux (Ubuntu 22.04 LTS hoặc mới hơn được khuyến nghị).
- **Phần mềm bắt buộc**:
  - Python 3.12 (`python3.12`, `python3.12-venv`, `python3.12-dev`)
  - Node.js v20.x trở lên và `npm` v10+
  - Git
  - (Tùy chọn cho tính năng AI): Ollama cài đặt cục bộ (`curl -fsSL https://ollama.com/install.sh | sh`)

---

## 2. Các Bước Cài Đặt Từng Lệnh (Step-by-Step Installation)

### Bước 1: Chuẩn bị mã nguồn và môi trường ảo Python
```bash
# Clone repository
git clone https://github.com/your-org/NetSentry.git
cd NetSentry

# Tạo môi trường ảo với Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Cài đặt chính xác các phụ thuộc backend (tuyệt đối không nâng cấp netmiko hoặc paramiko)
pip install -r backend/requirements.txt
```

### Bước 2: Cài đặt và build giao diện Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

### Bước 3: Kiểm tra tính sẵn sàng của môi trường
```bash
.venv/bin/python scripts/check_env.py
```
> [!NOTE]
> Kết quả mong đợi: `[SUCCESS] All environment requirements passed!` với `netmiko==4.8.0` và `paramiko==5.1.0`.

### Bước 4: Khởi tạo dữ liệu người dùng Demo
```bash
.venv/bin/python scripts/seed_demo.py --db backend/netsentry.db
```
Lệnh sẽ in ra thông tin đăng nhập ngẫu nhiên cho 3 tài khoản: `demo_admin`, `demo_operator`, `demo_viewer`.

### Bước 5: Chạy toàn bộ bài kiểm tra xác minh tổng thể
```bash
bash scripts/verify_all.sh
```

---

## 3. Khởi Chạy Hệ Thống Demo

### Lựa chọn A: Chạy với thiết bị giả lập (Không cần phần cứng router)
```bash
.venv/bin/python scripts/run_api_with_fake_device.py --fixture insecure --port 8000
```
Mở trình duyệt truy cập: `http://localhost:8000` (hoặc mở frontend dev server `cd frontend && npm run dev` tại `http://localhost:5173`).

### Lựa chọn B: Chạy hệ thống đầy đủ kết nối Lab Router thật
```bash
# 1. Cấu hình file backend/.env
cp backend/.env.example backend/.env
# Điền thông tin SSH router lab và bí mật snapshot

# 2. Khởi chạy Backend API
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --app-dir backend
```

---

## 4. Bảng Tra Cứu Sự Cố Thường Gặp (Troubleshooting Matrix)

| Hiện tượng / Triệu chứng | Nguyên nhân có thể | Cách xử lý |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'app'` | Thiếu biến môi trường `PYTHONPATH` hoặc chạy ngoài thư mục root | Chạy từ thư mục gốc repo hoặc thiết lập `export PYTHONPATH=backend:$PYTHONPATH` |
| `TypeError: FakeConnector.__init__()` | Phiên bản mã kiểm thử lệch cú pháp | Đảm bảo truyền đúng `config_text="..."` theo interface định nghĩa |
| `NETSENTRY_AUTH_DISABLED is strictly forbidden` | Biến môi trường xung đột giữa Public Mode và Auth Disabled | Kiểm tra file `.env`, đảm bảo nếu `NETSENTRY_PUBLIC_MODE=1` thì `NETSENTRY_AUTH_DISABLED=0` |
| `503 Service Unavailable` khi gọi `/explain` | Tiến trình Ollama chưa chạy hoặc chưa tải model | Khởi động Ollama: `ollama serve` và tải model: `ollama pull qwen2.5:7b` |
| `Device IP not in allowed network` | Địa chỉ IP router nằm ngoài dải cho phép | Khai báo dải mạng lab trong `NETSENTRY_ALLOWED_NETWORKS` (ví dụ: `192.168.1.0/24`) |
| `PLAN_HASH_MISMATCH` khi áp dụng bản vá | Template bị sửa đổi sau khi admin đã duyệt kế hoạch | Hủy kế hoạch cũ (`cancel`) và thực hiện đề xuất/phê duyệt lại từ đầu |
