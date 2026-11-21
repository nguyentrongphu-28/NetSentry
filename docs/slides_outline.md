# Dàn Ý Bài Thuyết Trình Đồ Án (Slide Presentation Outline)

Cấu trúc bài trình bày thuyết trình chuẩn gồm 10–12 slide, thời lượng trình bày 10–12 phút trước Hội đồng đánh giá đồ án.

---

## Slide 1: Tiêu Đề & Giới Thiệu (Title Slide)
- **Tên đề tài**: NetSentry - Nền Tảng Tự Động Hóa Kiểm Toán An Ninh & Khắc Phục Lỗi Cấu Hình Thiết Bị Mạng Cisco IOS Tuân Thủ CIS Benchmark
- **Thành viên thực hiện**: [Tên sinh viên, MSSV]
- **Giảng viên hướng dẫn**: [Tên GVHD]
- **Đơn vị đào tạo**: Khoa Mạng máy tính & Truyền thông / An toàn thông tin

## Slide 2: Đặt Vấn Đề & Động Lực Nghiên Cứu (Motivation & Problem Statement)
- Thách thức: Cấu hình thủ công trên hàng chục router dễ phát sinh sai sót an ninh nghiêm trọng (Telnet cleartext, password encryption tắt, SNMP default community).
- Thiếu hụt: Kiểm toán định kỳ bằng tay tốn thời gian; thiếu cơ chế kiểm soát 4 mắt (Four-Eyes Principle) khi thực thi sửa đổi trên hạ tầng mạng đang hoạt động.
- Giải pháp: Xây dựng nền tảng NetSentry tự động hóa toàn diện quy trình Kiểm toán -> Phát hiện sai lệch -> Hỗ trợ AI -> Khắc phục an toàn có xác minh.

## Slide 3: Mục Tiêu & Đóng Góp Của Đồ Án (Objectives & Contributions)
- Tự động hóa kiểm toán 8 quy tắc cốt lõi theo CIS Cisco IOS Benchmark.
- Cơ chế quản lý mốc chuẩn (Baseline & Drift) và che giấu bí mật cấu hình bằng HMAC-SHA256.
- Trợ lý AI cục bộ (Ollama) giải thích rủi ro bằng tiếng Việt với thiết kế phòng chống Prompt Injection tuyệt đối.
- Quy trình khắc phục lỗi an toàn với cơ chế phê duyệt 4 mắt, CAS Atomic Lock và tự động hoàn tác (Auto-Rollback).

## Slide 4: Kiến Trúc Hệ Thống & Ranh Giới Tin Cậy (System Architecture)
- Sơ đồ khối kiến trúc hệ thống (Mermaid diagram).
- Ranh giới tin cậy (Trust Boundaries) giữa Trình duyệt -> Backend API -> Ollama AI -> Cisco Router.
- Clean Architecture: Tuyệt đối không để module AI hoặc Remediation import thư viện SSH Connector.

## Slide 5: Thiết Kế Kiểm Toán & Động Cơ Quy Tắc (Audit Engine Design)
- 8 quy tắc CIS Benchmark (NET-001 đến NET-008).
- Kỹ thuật phân tích cú pháp AST cục bộ trong bộ nhớ (In-Memory AST Parsing).
- Tốc độ xử lý siêu nhanh (< 1ms cho mỗi cấu hình).
- Phân loại kết quả rõ ràng: `PASS`, `FAIL`, `UNKNOWN`.

## Slide 6: Cơ Chế Khắc Phục Lỗi An Toàn (Safe Remediation Workflow)
- Nguyên tắc Maker-Checker (4 mắt): Operator đề xuất -> Admin độc lập phê duyệt.
- Xác thực lại mật khẩu (Step-up Authentication) khi phê duyệt và áp dụng.
- Bảo vệ tính toàn vẹn bằng mã băm kế hoạch (`plan_hash`).
- Chu trình thực thi ngầm: Áp dụng lệnh -> Kiểm toán xác minh độc lập -> `write memory` hoặc `rollback`.

## Slide 7: Tích Hợp AI & Phòng Chống Tấn Công Prompt Injection (AI Security)
- Giải thích vì sao **AI chỉ giải thích rủi ro, không bao giờ sinh lệnh CLI**: Ngăn ngừa tấn công đầu độc chỉ dẫn qua banner router.
- Cơ chế kiểm chứng đầu ra `ExplanationValidator`: Lọc bỏ 100% dòng lệnh CLI và rule_id bịa đặt.
- Kết quả kiểm thử với 20 kịch bản Prompt Injection: Tỷ lệ an toàn đạt 100%.

## Slide 8: Ma Trận Đánh Giá Bảo Mật (Security Matrix S1–S15)
- Bảng tổng hợp 15 yêu cầu an toàn cốt lõi (S1 đến S15) kiểm thử tự động.
- 47 / 47 test nodes đạt yêu cầu (0 trượt, 0 GAP).
- Phủ kín: RBAC, CSRF, Chống Brute-force, Session, Che rò rỉ bí mật, Chế độ công khai (Public Mode).

## Slide 9: Kết Quả Thực Nghiệm & Đánh Giá Độ Chính Xác (Evaluation Results)
- Kết quả đo lường trên tập Corpus đóng băng độc lập (`MANIFEST.sha256`):
  - Macro-average Precision: **100.0%**
  - Macro-average Recall: **100.0%**
  - Macro-average F1-Score: **1.000**
- Tỷ lệ rò rỉ bí mật: **0.0%**.
- Số liệu đo lường hiệu năng và thông lượng hệ thống.

## Slide 10: Demo Hệ Thống (Live / Recorded Demo)
- Video demo 5–7 phút hoặc thao tác trực tiếp trên giao diện:
  1. Operator kiểm toán router -> Phát hiện lỗi NET-008 FAIL.
  2. AI giải thích rủi ro.
  3. Operator đề xuất bản vá -> Thử tự duyệt bị chặn.
  4. Admin duyệt kèm mật khẩu -> Apply bản vá.
  5. Hệ thống xác minh thành công -> Đổi sang FIXED trong bảng Compare.

## Slide 11: Hạn Chế Hiện Tại & Hướng Phát Triển (Limitations & Future Work)
- Hạn chế: Mới hỗ trợ nền tảng Cisco IOS; 2 mẫu sửa lỗi tự động; kiến trúc đơn tiến trình.
- Hướng phát triển: Hỗ trợ đa nền tảng (Cisco IOS-XE, NX-OS, Arista, Juniper); tích hợp SSO/MFA; mở rộng quy tắc định tuyến OSPF/BGP.

## Slide 12: Tổng Kết & Q&A (Conclusion & Q&A)
- Đồ án đã hoàn thành 100% các tiêu chí nghiệm thu đề ra.
- Lời cảm ơn Hội đồng và mở phần hỏi đáp (Q&A).
