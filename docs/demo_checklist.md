# Danh Sách Kiểm Tra Trước & Sau Trình Diễn (Demo Checklist)

Bảng kiểm tra (checklist) bắt buộc dành cho đội ngũ phát triển trước khi bước vào buổi bảo vệ đồ án hoặc ghi hình video demo.

---

## 1. Danh Sách Kiểm Tra Trước Khi Trình Diễn (Pre-Demo Checklist)

- [ ] **Môi trường & Mã nguồn**:
  - [ ] Đã chạy kiểm tra môi trường: `.venv/bin/python scripts/check_env.py` (báo [SUCCESS]).
  - [ ] Chạy lệnh tổng kiểm tra: `bash scripts/verify_all.sh` (tất cả các bước đều vượt qua).
  - [ ] Kho mã đã commit đầy đủ, không còn thay đổi dở dang (`git status` clean).
  - [ ] Gắn git tag phiên bản demo: `git tag v0.1.0-demo`.
- [ ] **Tài khoản & Dữ liệu**:
  - [ ] Đã chạy `scripts/seed_demo.py` để tạo tài khoản sạch (`demo_admin`, `demo_operator`, `demo_viewer`).
  - [ ] Đã lưu trữ mật khẩu demo vào sổ tay (không dán lên màn hình chiếu).
  - [ ] Bật chế độ `NETSENTRY_ENABLE_DOCS=0` nếu chạy qua Cloudflare Quick Tunnel.
- [ ] **Thiết bị Mạng & Phòng Lab**:
  - [ ] Đã sao lưu (backup) cấu hình router lab ra file an toàn.
  - [ ] Có dây cáp Console dự phòng cắm sẵn vào router để xử lý khẩn cấp nếu mất kết nối SSH.
  - [ ] Đã kiểm tra địa chỉ IP router lab nằm đúng trong dải `NETSENTRY_ALLOWED_NETWORKS`.
  - [ ] Đã kiểm tra cấu hình ban đầu của router lab có chứa `ip http server` để demo lỗi NET-008.
- [ ] **Bảo Mật Màn Hình & Trình Duyệt**:
  - [ ] Tắt toàn bộ thông báo hệ thống (Telegram, Zalo, Email, Slack...).
  - [ ] Sử dụng cửa sổ trình duyệt ẩn danh (Incognito Window) để tránh autofill mật khẩu cá nhân.
  - [ ] Kiểm tra màn hình không để lộ mật khẩu, enable secret, cookie hoặc SSH private key.

---

## 2. Danh Sách Kiểm Tra Sau Khi Trình Diễn (Post-Demo Checklist)

- [ ] **Thu hồi quyền truy cập & Khôi phục**:
  - [ ] Tắt tiến trình `cloudflared` (nếu có sử dụng tunnel công khai).
  - [ ] Tắt tiến trình backend server: đặt `NETSENTRY_REMEDIATION_EXECUTE_MODE=off`.
  - [ ] Khôi phục cấu hình router lab về trạng thái chuẩn ban đầu của nhà trường/phòng thí nghiệm.
  - [ ] Xoay vòng (rotate) hoặc xóa mật khẩu tài khoản demo và tài khoản SSH thử nghiệm trên router.
- [ ] **Kiểm tra an toàn nhật ký**:
  - [ ] Truy xuất bảng `security_events` và `audit_runs` để rà soát toàn bộ nhật ký phiên demo, đảm bảo không có bất thường rò rỉ.
  - [ ] Đóng kết nối SSH và dọn dẹp các tệp tạm trong thư mục `tmp/`.
