# Dàn Ý Báo Cáo Đồ Án NetSentry (Final Report Outline)

Dàn ý cấu trúc chuẩn cho quyển báo cáo đồ án tốt nghiệp / đồ án môn học NetSentry, bám sát đề xuất ban đầu và tiến trình triển khai thực tế.

---

## Chương 1: Giới Thiệu & Tổng Quan Đề Tài (Introduction)
1. **Bối cảnh đề tài**:
   - Tầm quan trọng của an ninh cấu hình mạng trong hạ tầng doanh nghiệp.
   - Các nguy cơ từ sai sót cấu hình (Misconfiguration) trên thiết bị định tuyến Cisco.
2. **Tổng quan các tiêu chuẩn an ninh**:
   - Giới thiệu bộ chuẩn CIS Cisco IOS Benchmark.
   - So sánh với các chuẩn phổ biến khác (NIST, DISA STIG).
3. **Mục tiêu và phạm vi của đồ án**:
   - Xây dựng nền tảng kiểm toán tự động, độc lập, bảo mật cao.
   - Hỗ trợ phát hiện sai lệch mốc chuẩn (Baseline & Drift), trợ lý AI giải thích rủi ro.
   - Quy trình khắc phục lỗi an toàn với cơ chế kiểm soát 4 mắt (Maker-Checker).

## Chương 2: Phân Tích Yêu Cầu & Mô Hình Đe Dọa (Requirements & Threat Model)
1. **Phân tích yêu cầu chức năng**:
   - Yêu cầu kết nối SSH chỉ đọc, kiểm toán 8 quy tắc CIS.
   - Phân quyền theo vai trò (RBAC): Viewer, Operator, Admin.
   - Quản lý phiên bản cấu hình (Snapshot HMAC Redaction).
2. **Mô hình đe dọa (Threat Modeling)**:
   - Nhận diện tài sản cần bảo vệ (Credentials, Running-Config, Session).
   - Phân tích mối đe dọa theo mô hình STRIDE rút gọn.
   - Thiết kế ranh giới tin cậy (Trust Boundaries) và 15 yêu cầu an toàn cốt lõi (S1–S15).

## Chương 3: Kiến Trúc Hệ Thống & Thiết Kế Bảo Mật (System Architecture & Security Design)
1. **Kiến trúc tổng thể**:
   - Sơ đồ khối các thành phần (Frontend SPA, Backend REST API, SQLite, Ollama LLM, Cisco Router).
2. **Thiết kế Clean Architecture & Cách ly bảo mật**:
   - Cách ly tuyệt đối giữa gói AI / Remediation và SSH Connectors.
   - Bộ lọc Allowlist lệnh CLI nghiêm ngặt.
3. **Quy trình kiểm toán và khắc phục 4 mắt (Remediation Lifecycle)**:
   - Máy trạng thái kế hoạch sửa đổi (State Machine).
   - Cơ chế bảo vệ tính toàn vẹn băm (`plan_hash`) và Atomic CAS Lock.
   - Vòng lặp: Áp dụng -> Kiểm toán xác minh -> Lưu cấu hình hoặc Hoàn tác tự động.
4. **Mô hình dữ liệu quan hệ (ERD)**:
   - Thiết kế các bảng: `users`, `devices`, `audit_runs`, `findings`, `snapshots`, `baselines`, `remediation_plans`, `remediation_executions`, `security_events`.

## Chương 4: Hiện Thực Hóa Hệ Thống (Implementation Details)
1. **Xây dựng bộ quy tắc kiểm toán CIS Benchmark**:
   - Cài đặt 8 quy tắc NET-001 đến NET-008 bằng kỹ thuật phân tích cú pháp AST in-memory.
2. **Cơ chế che giấu bí mật (Config Redactor & Normalizer)**:
   - Thuật toán che giấu HMAC-SHA256 bảo vệ mật khẩu và chuỗi cộng đồng SNMP.
3. **Tích hợp mô hình ngôn ngữ lớn (LLM)**:
   - Kỹ thuật thiết kế prompt an toàn và bộ lọc kiểm chứng đầu ra `ExplanationValidator`.
4. **Giao diện người dùng Web (Frontend)**:
   - Trải nghiệm người dùng, phân tách quyền hiển thị giao diện theo vai trò.

## Chương 5: Đánh Giá Thực Nghiệm & Kết Quả (Evaluation & Results)
1. **Phương pháp đánh giá & Bộ dữ liệu kiểm tra**:
   - Giới thiệu Corpus cấu hình độc lập đóng băng (`MANIFEST.sha256`).
   - Định nghĩa các số liệu đo lường: Confusion Matrix, Wilson 95% Confidence Interval.
2. **Kết quả đo lường độ chính xác quy tắc**:
   - Bảng tổng hợp TP/FP/FN/TN, Precision, Recall, F1 trên tập kiểm tra.
3. **Kết quả ma trận kiểm thử an toàn (S1–S15)**:
   - Báo cáo chi tiết 47 pytest test nodes đạt 100%, 0 khoảng trống (GAPs).
4. **Đánh giá an toàn AI**:
   - Thử nghiệm 20 trường hợp tấn công prompt injection qua cấu hình router.
5. **Đo lường hiệu năng & Thử nghiệm phòng Lab**:
   - Thời gian phân tích của Engine (< 1ms).
   - Số liệu kiểm nghiệm thực tế trên router phòng lab.

## Chương 6: Hạn Chế & Hướng Phát Triển (Limitations & Future Work)
1. **Các hạn chế hiện tại**:
   - Chỉ hỗ trợ nền tảng Cisco IOS; 2 template sửa đổi tự động; kiến trúc đơn tiến trình.
2. **Hướng phát triển tương lai**:
   - Mở rộng hỗ trợ đa nền tảng (Cisco IOS-XE, NX-OS, Arista, Juniper).
   - Tích hợp xác thực tập trung SSO (SAML/OIDC) và MFA.
   - Mở rộng các quy tắc CIS cho giao thức định tuyến và bảo mật lớp mạng sâu.

## Kết Luận & Tài Liệu Tham Khảo (Conclusion & References)
- Tóm tắt các kết quả đạt được.
- Danh mục tài liệu tham khảo (CIS Benchmarks, NIST SP 800-115, OWASP Top 10 LLM).
