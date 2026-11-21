# Các Hạn Chế Của Hệ Thống (System Limitations)

Tài liệu ghi nhận một cách trung thực, minh bạch các giới hạn về phạm vi thiết bị, quy tắc kiểm toán, cơ chế khắc phục, kiến trúc hạ tầng và các kịch bản chưa được kiểm thử trong đồ án NetSentry.

---

## 1. Giới Hạn Về Nền Tảng Thiết Bị & Quy Tắc Kiểm Toán

1. **Hỗ trợ độc quyền nền tảng `cisco_ios`**:
   - Hiện tại NetSentry chỉ xây dựng connector và parser cho hệ điều hành Cisco IOS (phiên bản 15.x / 12.x). Các nền tảng khác như Cisco NX-OS, Cisco IOS-XE nâng cao, Arista EOS, Juniper JunOS hay thiết bị Linux chưa được hỗ trợ.
2. **Phạm vi 8 quy tắc CIS Benchmark**:
   - Hệ thống mới triển khai 8 quy tắc cốt lõi (NET-001 đến NET-008) liên quan đến quản trị dịch vụ (Telnet, SSH v2, HTTP), xác thực (Enable Secret, Password Encryption), đường truyền VTY (Timeout, ACL) và giám sát (SNMP). Chưa bao gồm các quy tắc sâu về giao thức định tuyến (OSPF/BGP authentication), NTP, Syslog mã hóa hay Control Plane Policing (CoPP).
3. **Mẫu khắc phục tự động (Remediation Templates)**:
   - Chỉ có 2 quy tắc hỗ trợ đề xuất và áp dụng sửa đổi tự động: `NET-008` (tắt HTTP server) và `NET-004` (bật mã hóa mật khẩu).
   - Trong đó: `NET-008` có khả năng hoàn tác đảo ngược (`no ip http server` <-> `ip http server`), còn `NET-004` là **bất khả nghịch** (Cisco IOS không có lệnh `no service password-encryption` để hoàn tác giải mã các mật khẩu đã bị xáo trộn type 7).
   - 6 quy tắc còn lại cung cấp tài liệu hướng dẫn thủ công (Manual Guidance) thay vì áp dụng tự động để tránh nguy cơ gián đoạn quản trị (ví dụ: ngắt kết nối SSH hiện hành nếu ACL cấu hình sai).

---

## 2. Giới Hạn Về Kiến Trúc & Triển Khai

1. **Kiến trúc đơn tiến trình (Single-Process Concurrency)**:
   - Hệ thống sử dụng SQLite làm cơ sở dữ liệu nhúng và `ThreadPoolExecutor(max_workers=1)` cho tiến trình chạy nền khắc phục lỗi. Không hỗ trợ chạy song song nhiều worker backend hoặc triển khai phân tán (multi-node cluster).
2. **Cơ chế xác thực & Quản lý phiên**:
   - Xác thực dựa trên bảng người dùng nội bộ SQLite và Argon2id. Chưa hỗ trợ Single Sign-On (SSO) qua SAML / OIDC / OAuth2 hoặc xác thực đa yếu tố (MFA / 2FA) qua TOTP/WebAuthn.
   - Cơ chế giới hạn tốc độ (Rate Limiting) lưu trong RAM tiến trình, do đó sẽ reset khi server khởi động lại.
3. **Mô hình AI & LLM**:
   - Chất lượng giải thích tiếng Việt phụ thuộc vào mô hình Ollama cục bộ (ví dụ: Qwen 2.5 7B). Trên các máy tính cấu hình thấp không có GPU chuyên dụng, thời gian sinh giải thích có thể kéo dài (từ 5 đến 15 giây).
   - AI chỉ giữ vai trò hỗ trợ đọc hiểu; không được cấp quyền tự động ra quyết định hay can thiệp vào tiến trình cấu hình router.
4. **Che giấu dữ liệu nhạy cảm (Config Redactor)**:
   - Sử dụng các biểu thức chính quy (Regex) và từ khóa tiêu chuẩn của Cisco IOS (`password`, `secret`, `community`). Nếu quản trị viên sử dụng các cú pháp phi chuẩn hoặc comment tùy biến chứa mật khẩu, biểu thức chính quy có thể không che phủ hết 100%.

---

## 3. Danh Sách Đã Kiểm Thử & Chưa Kiểm Thử (Tested vs Untested Matrix)

| Hạng mục | Đã kiểm thử (Tested) | Chưa kiểm thử (Untested) |
| :--- | :--- | :--- |
| **Phần cứng / Mô phỏng** | Cấu hình Cisco IOS 15.2, FakeConnector, Lab Cisco 2911 / 1941 thật, PNETLab / GNS3 | Switch Layer 3 Catalyst 3850/9300, Router Cisco ISR 4000 series chạy IOS-XE |
| **Hệ điều hành máy chủ** | Linux Ubuntu 22.04 LTS / Debian x86_64 | Windows Server, macOS Apple Silicon (ARM64) |
| **Trình duyệt web** | Google Chrome 120+, Mozilla Firefox 120+ | Apple Safari, Microsoft Edge trên mobile |
| **Tải kiểm thử** | Kiểm toán tuần tự từng thiết bị, tối đa 50 audit runs lưu trong DB | Kiểm toán đồng thời hàng trăm router trong mạng doanh nghiệp lớn |
