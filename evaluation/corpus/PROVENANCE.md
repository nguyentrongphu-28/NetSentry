# Corpus Provenance & Ground Truth Labeling Record

## 1. Nguồn Gốc Cấu Hình (Configuration Sources)

Tập corpus được chia làm hai phân vùng: `dev/` (dùng để phát triển và tinh chỉnh rules) và `test/` (đóng băng để đánh giá chính thức độc lập).

| Tệp | Phân vùng | Loại | Mô tả |
| :--- | :---: | :---: | :--- |
| `dev/r1_secure.cfg` | dev | Tổng hợp (Synthetic) | Cấu hình baseline an toàn, tuân thủ cả 8 rule CIS Cisco IOS. |
| `dev/r2_insecure.cfg` | dev | Tổng hợp (Synthetic) | Cấu hình kế thừa yếu kém, vi phạm cả 8 rule. |
| `dev/r3_edge_cases.cfg` | dev | Tổng hợp (Synthetic) | Trường hợp biên: `exec-timeout 15 0`, `transport input ssh telnet`. |
| `dev/r4_mixed_vty.cfg` | dev | Tổng hợp (Synthetic) | Trường hợp nhiều khối `line vty` (0-4 vs 5-15) với thiết lập khác nhau. |
| `test/r1_core.cfg` | test | Tổng hợp / Trích xuất Lab | Router phân vùng Core: telnet, không mã hóa mật khẩu, SNMP RW. |
| `test/r2_hardened.cfg` | test | Tổng hợp / Trích xuất Lab | Router phân vùng Edge được gia cố chuẩn an toàn toàn diện. |
| `test/r3_insecure_vty.cfg` | test | Tổng hợp (Synthetic) | Vi phạm giao thức và xác thực truy cập từ xa VTY. |
| `test/r4_snmp_http.cfg` | test | Tổng hợp (Synthetic) | Bật HTTP server không an toàn và SNMP community RW. |

---

## 2. Quy Trình Gán Nhãn & Thống Nhất (Labeling Protocol)

1. **Phương pháp**: Nhãn đúng trong `labels.json` được hai kỹ sư mạng/bảo mật gán độc lập dựa hoàn toàn vào tiêu chuẩn trong `rules_catalog.md`. Tuyệt đối không sử dụng kết quả chạy engine để gán nhãn tự động.
2. **Tỷ lệ đồng thuận ban đầu**: 100% (64/64 cặp rule-file thống nhất).
3. **Che bí mật (Redaction)**: Tất cả chuỗi nhạy cảm (community string, enable secret thật, private key) đều được thay thế bằng nhãn `<REDACTED>` hoặc hash mẫu dummy trước khi đưa vào repo.
4. **Đóng băng tập test**: Tập `test/` và phân đoạn `test/` trong `labels.json` được tính băm SHA-256 lưu trong `MANIFEST.sha256`. Bất kỳ sửa đổi nào trên tập test sau khi đóng băng sẽ bị công cụ `rule_eval.py` từ chối thực thi.
