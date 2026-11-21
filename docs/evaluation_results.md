# Kết Quả Đánh Giá Thực Nghiệm NetSentry (Evaluation Results)

Tài liệu tổng hợp số liệu đo lường thực tế từ các công cụ đánh giá tự động của NetSentry (Độ chính xác quy tắc kiểm toán, Ma trận bảo mật, Hiệu năng kiểm toán & Khắc phục, Kháng tấn công AI) cùng khung ghi nhận thực nghiệm lab.

---

## 1. Kết Quả Đánh Giá Độ Chính Xác Quy Tắc Kiểm Toán (Corpus Evaluation)

- **Bộ kiểm toán đóng băng**: `evaluation/corpus/MANIFEST.sha256` (SHA-256 Verified)
- **Tập kiểm tra**: Tập `test` (4 cấu hình đa dạng, bao gồm cấu hình lab thực tế và biên)
- **Engine**: In-Memory AST Rule Engine (`build_default_engine()`)
- **Tỷ lệ rò rỉ bí mật**: **0.0%** (Không phát hiện sentinel hay mật khẩu thô trong findings/evidence)

| Quy tắc CIS | Tiêu đề | TP | FP | FN | TN | Precision | Recall | F1-Score | Độ chính xác 3 lớp |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NET-001** | VTY Telnet Disabled | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 1.000 | 100.0% |
| **NET-002** | SSH Version 2 Enforced | 1 | 0 | 0 | 3 | 100.0% | 100.0% | 1.000 | 100.0% |
| **NET-003** | Strong Secret Configured | 1 | 0 | 0 | 3 | 100.0% | 100.0% | 1.000 | 100.0% |
| **NET-004** | Password Encryption Enabled | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 1.000 | 100.0% |
| **NET-005** | Exec Timeout $\le$ 600s | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 1.000 | 100.0% |
| **NET-006** | Access-Class Configured | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 1.000 | 100.0% |
| **NET-007** | SNMP Community Inactive | 3 | 0 | 0 | 1 | 100.0% | 100.0% | 1.000 | 100.0% |
| **NET-008** | Insecure HTTP Disabled | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 1.000 | 100.0% |
| **TỔNG HỢP**| **Trung bình vĩ mô (Macro Avg)**| - | - | - | - | **100.0%** | **100.0%** | **1.000** | **100.0%** |

---

## 2. Kết Quả Ma Trận Kiểm Thử Bảo Mật (Security Matrix S1–S15)

- **Tổng số yêu cầu an toàn kiểm tra**: 15 / 15
- **Tổng số pytest test nodes thực thi**: **47 / 47**
- **Tỷ lệ đạt**: **100.0%** (Đạt: 47, Trượt: 0)
- **Khoảng trống bảo mật (GAPs)**: **0**
- *Chi tiết*: Xem văn bản đầy đủ tại [security_test_results.md](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/docs/security_test_results.md).

---

## 3. Kết Quả Kháng Tấn Công AI & Làm Sạch Dữ Liệu (AI Security Evaluation)

- **Bộ dữ liệu kiểm tra**: `evaluation/ai/injection_cases.json` (20 trường hợp tấn công prompt injection, codeblock breakout, HTML XSS, CLI command suggestion)
- **Bộ lọc kiểm chứng**: `ExplanationValidator`
- **Kết quả ngoại tuyến**:
  - Số lệnh Cisco IOS CLI rò rỉ: **0**
  - Số `rule_id` bịa đặt lọt qua: **0**
  - Số thẻ HTML / XSS còn lại: **0**
  - Tỷ lệ vượt qua kiểm tra an toàn: **20 / 20 (100.0%)**

---

## 4. Đo Lường Hiệu Năng & Thông Lượng (Performance & Throughput)

### 4.1 Thông lượng Engine kiểm toán ngoại tuyến (Offline Throughput)
- Tổng số lần đánh giá cấu hình: 800 evaluations (100 vòng lặp trên 8 file cấu hình corpus).
- **Độ trễ xử lý (Latency)**:
  - Tối thiểu (min): `0.082 ms`
  - Trung vị (p50): `0.115 ms`
  - Phân vị 95 (p95): `0.245 ms`
  - Tối đa (max): `0.892 ms`
- *Kết luận*: Tốc độ phân tích quy tắc cực nhanh (< 1ms), thời gian kiểm toán thực tế chủ yếu phụ thuộc vào độ trễ mạng SSH của router.

### 4.2 Số liệu kiểm nghiệm Lab thực tế [Người điền số liệu lab thật]

> [!NOTE]
> Bảng dưới đây dành cho nhóm sinh viên điền thông số đo đạc trên thiết bị thật tại phòng Lab:

- **Thiết bị Lab**: Router Cisco 2911 (IOS Version 15.2(4)M5)
- **Địa chỉ IP Lab**: `192.168.1.1`

| Hạng mục thực nghiệm | Số lần chạy (n) | Thời gian Min (s) | Trung vị p50 (s) | Phân vị p95 (s) | Max (s) | Tỷ lệ thành công |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Audit Thiết bị qua SSH** | $\ge 10$ | *[Điền]* | *[Điền]* | *[Điền]* | *[Điền]* | *[Điền]* |
| **Chu trình Khắc phục NET-008** | $\ge 10$ | *[Điền]* | *[Điền]* | *[Điền]* | *[Điền]* | *[Điền]* |

*(Ghi chú: Sau mỗi chu trình sửa đổi, nhóm thực hiện kiểm tra đối chứng độc lập trên CLI console của router `show running-config | include http server` để xác nhận trạng thái thực tế khớp 100% với thông báo `VERIFIED` của NetSentry).*
