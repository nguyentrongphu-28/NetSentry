# Báo cáo gộp & rà soát tích hợp (code A tuần 3–6 + AI assistant tuần 7)

## 1. Tuần 7 có phù hợp không?

**Có**, với kế hoạch tuần 7 (cột A/B/C + "cả nhóm") và proposal (AI giải thích, đề xuất có cấu trúc, không tự thực thi, test prompt injection/quyền/lỗi):
AI không có đường SSH (test AST), mọi đầu ra qua validator, lệnh chỉ trong allowlist, thay đổi vẫn đi qua Preview → Validate → Approve → Execute → Verify.
Dữ liệu dùng chung (`rules.json`, `lab_policy.json`, 5 file cấu hình mẫu) **giống hệt** bản của A (đã diff). Module tuần 7 chạy độc lập 57/57.
Nhưng tuần 7 được viết khi **chưa có code của A**, nên chưa từng chạy với finding thật → các lỗi tích hợp dưới đây.

## 2. Lỗi tìm thấy & đã sửa

| # | Mức | Lỗi | Sửa | Test hồi quy |
|---|---|---|---|---|
| 1 | **Cao (bảo mật, code A)** | Cổng "chỉ cho phép `show`" của `NetworkAdapter.run_show` dùng `\s` nên `show version\nreload` (xuống dòng) **lọt qua** → có thể đưa lệnh ghi vào đường chỉ-đọc | Regex chỉ dùng dấu cách thường + `fullmatch` | `test_run_show_blocks_newline_injection` |
| 2 | **Cao (rò bí mật, code A)** | `sanitizer`: `ntp authentication-key 1 md5 KEY` che nhầm chữ `md5`, **khóa thật còn nguyên** trong snapshot | Mẫu riêng cho NTP đặt trước mẫu chung; thêm `wpa-psk` | `test_sanitizer_masks_ntp_key_not_algorithm` |
| 3 | Cao (tích hợp) | Tên action lệch: AI đề xuất `create_vlan_access_port`, A dùng `create_vlan_assign_access_port` → B không khớp được đề xuất của AI | Đổi AI theo tên của A | `test_int_action_type_matches_task_template` |
| 4 | Trung bình | Fallback tuần 7 làm **rơi dòng remediation hợp lệ** (SEC-004 mất nội dung banner, SEC-009 mất `interface <tên-interface>`) → hướng dẫn thiếu/sai ngữ cảnh | Fallback cho phép dòng remediation của chính rules.json (vẫn chặn bí mật/lệnh nguy hiểm) | `test_int_fallback_keeps_every_remediation_line_and_is_valid` |
| 5 | Thấp | `PolicyGate` dùng `$` nên chấp nhận tên VLAN `"LAB\n"` (A thì từ chối) | `fullmatch` + từ chối ký tự điều khiển | `test_int_policy_gate_agrees_with_task_template` (lưới 1.000+ tổ hợp) |
| 6 | Thấp | `make_client_from_env()` không nạp `.env`; thiếu key → `KeyError`, timeout sai → `ValueError` | Nạp `.env` (`app/core/env.py`), báo `RuntimeError` rõ ràng | — |
| 7 | Thấp | Test kiến trúc "AI không import thiết bị" chỉ xét phần đầu tên module → `from app.devices.network_adapter import …` **không bị bắt** sau khi đổi sang gói | Kiểm tra mọi đoạn của đường dẫn import | `test_arch_no_device_or_shell_imports` |

## 3. Kết quả
`python scripts/run_all_tests.py`: tuần 3 = 18, tuần 4 = 15, tuần 5 = 12, tuần 6 = 26, tuần 7 = 57, tích hợp = 6 → **134 test đạt**.
Với 33 finding FAIL thật do `evaluate_config()` sinh ra: 33/33 được chấp nhận ở đường LLM (mock) và 33/33 fallback hợp lệ.

## 4. Còn tồn tại (cần người thật xử lý — không thể sửa bằng code)
* **Chưa chạy thiết bị thật** (A, tuần 5–6) và **chưa gọi LLM thật** (tuần 7; `python scripts/run_ai_eval.py --live` khi có key).
* `validate_ios_syntax(..., policy=None)` bỏ qua kiểm tra dải VLAN/port: B **bắt buộc** truyền `policy` khi gọi.
* `lab_policy.json` vẫn là giá trị VÍ DỤ (VLAN 20–29, Gi0/1–2); `protected_interfaces` đang rỗng — cần quản lý lab xác nhận.
* `NetworkAdapter.apply_config` tin người gọi đã validate; B phải luôn gọi `validate_ios_syntax` ngay trước khi execute.
* Backend FastAPI/DB/RBAC (B) và frontend (C) chưa có: `backend/app/api`, `core/auth`, `db`, `frontend/` còn trống.
* Rule SEC-003 (`exec-timeout` mặc định không hiện trong running-config) có thể báo sai trên thiết bị thật — xem `REVIEW_TUAN_1-6.md` mục 3.
