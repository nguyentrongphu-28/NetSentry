# Mô Hình Đe Dọa NetSentry (Threat Model)

Tài liệu phân tích tài sản bảo mật, bề mặt tấn công, ranh giới tin cậy, các mối đe dọa tiềm tàng theo phân loại STRIDE rút gọn, các biện pháp giảm thiểu được kiểm chứng qua mã kiểm thử bảo mật S1–S15, và các rủi ro còn lại (residual risks).

---

## 1. Phân Loại Tài Sản Cần Bảo Vệ (Protected Assets)

1. **Thông tin xác thực thiết bị (Device Credentials)**: Mật khẩu SSH, Enable Secret của router/switch mạng.
2. **Cấu hình thiết bị mạng thô (Raw Device Running-Config)**: Chứa topology mạng, địa chỉ IP nội bộ, access-list, mật khẩu xáo trộn (type 7) hoặc mã hóa (type 5/8/9).
3. **Tài khoản và phiên người dùng (User Accounts & Sessions)**: Tài khoản quản trị (admin), vận hành (operator), người xem (viewer), mật khẩu băm Argon2id, cookie phiên bảo mật.
4. **Tính toàn vẹn kiểm toán & khắc phục (Audit & Remediation Integrity)**: Kết quả đánh giá 8 CIS rules, tính bất biến của kế hoạch sửa lỗi sau khi phê duyệt, nhật ký kiểm toán (security audit events).

---

## 2. Phân Tích Mối Đe Dọa STRIDE & Biện Pháp Giảm Thiểu

| Mã STRIDE | Mối đe dọa (Threat) | Kịch bản tấn công | Biện pháp giảm thiểu (Mitigation) | Test chứng minh |
| :---: | :--- | :--- | :--- | :---: |
| **S** (Spoofing) | Giả mạo người dùng / Chiếm phiên | Kẻ tấn công truy cập API trái phép không thông qua đăng nhập hoặc đoán session cookie. | Bắt buộc xác thực mọi route (trừ `/health` & `/auth/login`); Session ID 256-bit ngẫu nhiên lưu bằng cookie `HttpOnly`, `SameSite=Lax`. | **S1**, **S5** |
| **T** (Tampering) | Chèn lệnh độc hại vào kế hoạch sửa đổi | Kẻ tấn công sửa lệnh trong kế hoạch sau khi admin đã phê duyệt (ví dụ đổi thành `reload`). | Tính toán và xác minh `plan_hash` (HMAC/SHA256) trên các trường cốt lõi trước khi apply. Khóa trạng thái CAS Atomic Lock. | **S10**, **S11** |
| **T** (Tampering) | Đột phá lệnh qua Connector | Kẻ tấn công mượn connector đọc để gửi lệnh cấu hình hoặc gửi lệnh nguy hiểm ngoài allowlist. | Connector đọc từ chối tuyệt đối mọi lệnh cấu hình; ConfigWriter áp dụng allowlist nghiêm ngặt trước khi chạm thiết bị. | **S7** |
| **R** (Repudiation) | Chối bỏ trách nhiệm hành động nhạy cảm | Người dùng tự đề xuất rồi tự phê duyệt, hoặc phủ nhận việc đã áp dụng thay đổi cấu hình mạng. | Ghi vết nhật ký sự kiện bảo mật đầy đủ (`security_events`); bắt buộc kiểm soát 4 mắt (Maker-Checker); re-auth mật khẩu khi phê duyệt/áp dụng. | **S12** |
| **I** (Information Disclosure) | Rò rỉ bí mật trong response / logs | Mật khẩu thiết bị, enable secret hoặc token hiển thị trong log, database, hoặc API response. | Áp dụng `ConfigRedactor` che toàn bộ sentinels; che giấu thông báo lỗi máy chủ nội bộ (500 Internal Server Error). | **S6** |
| **I** (Information Disclosure) | Lộ cấu hình qua chế độ công khai | Kẻ tấn công quét các endpoint lấy running-config thô khi server mở ra Internet qua Tunnel. | Chế độ `NETSENTRY_PUBLIC_MODE=1` tự động tắt `/docs`, `/redoc`, chặn API đọc nội dung snapshot thô, từ chối khởi động nếu tắt auth. | **S13** |
| **D** (Denial of Service) | Tấn công dò mật khẩu (Brute-Force) | Kẻ tấn công gửi hàng nghìn request login để vét cạn mật khẩu tài khoản. | Khóa tài khoản tạm thời sau số lần thử sai liên tiếp; Rate-limiter trượt theo IP nguồn. | **S4** |
| **E** (Elevation of Privilege) | Vượt quyền theo vai trò (RBAC Bypass) | Viewer gọi API áp dụng bản vá, hoặc Operator tự duyệt kế hoạch. | Kiểm tra ma trận quyền hạn nghiêm ngặt ở lớp middleware dependency FastAPI; kiểm tra xác thực vai trò cấp hạt nhân. | **S2** |
| **E** (Elevation of Privilege) | Tấn công Prompt Injection qua AI | Cấu hình mạng độc hại chứa chỉ dẫn nhằm thao túng AI sinh lệnh hạ độc hệ thống. | Thiết kế cách ly hoàn toàn (Clean Architecture): AI **chỉ giải thích**, không bao giờ sinh lệnh CLI; validator lọc 100% lệnh CLI và rule_id bịa. | **S8**, **S9**, **S15** |
| **E** (Elevation of Privilege) | Tấn công leo thang SSRF & Traversal | Kẻ tấn công nhập IP nội bộ nhạy cảm hoặc đường dẫn file `../../etc/passwd` trong device ID / host. | Danh sách trắng mạng quản trị (`allowed_networks`); regex kiểm tra device_id ngăn chặn path traversal. | **S14** |

---

## 3. Rủi Ro Còn Lại (Residual Risks) & Khuyến Nghị Vận Hành

1. **Cloudflare Quick Tunnel**:
   - *Rủi ro*: Quick Tunnel ngẫu nhiên không có cam kết SLA và có thể bị trỏ lại URL mới khi tiến trình khởi động lại. Lưu lượng TLS đi qua hạ tầng Cloudflare.
   - *Khuyến nghị*: Không dùng cho môi trường sản xuất dài hạn. Cần chuyển sang Named Tunnel có xác thực Access (Zero Trust) hoặc VPN nội bộ.
2. **Rate Limiting Trong Bộ Nhớ (In-Memory Limiter)**:
   - *Rủi ro*: Khi tiến trình backend khởi động lại, bộ đếm số lần đăng nhập sai và cửa sổ trượt của IP bị xóa rỗng.
   - *Khuyến nghị*: Triển khai Redis hoặc persistent key-value store nếu cần mở rộng nhiều instance.
3. **SQLite Đơn Tiến Trình (Single-Process Concurrency)**:
   - *Rủi ro*: SQLite hỗ trợ đa đọc nhưng tuần tự hóa khi ghi; khóa cơ sở dữ liệu có thể bị nghẽn nếu quá nhiều thiết bị kiểm toán đồng thời.
   - *Khuyến nghị*: Duy trì giới hạn tiến trình nền hiện tại (Single background executor worker cho remediation).
4. **Tài Khoản Ghi SSH Có Quyền Hạn Cao (High-Privilege Write Account)**:
   - *Rủi ro*: Thông tin tài khoản ghi cấu hình (`NETSENTRY_SSH_WRITE_*`) nếu bị lộ từ file `.env` trên máy chủ sẽ ảnh hưởng trực tiếp đến router.
   - *Khuyến nghị*: Phân quyền file `.env` chỉ người dùng chạy dịch vụ (`chmod 600`), sử dụng Ansible Vault hoặc Secret Manager chuyên dụng trong môi trường doanh nghiệp.
