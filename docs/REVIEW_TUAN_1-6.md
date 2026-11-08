# Rà soát Tuần 1–6 và khả năng chạy trên thiết bị thật

> **Cập nhật khi gộp repo:** code Python của A đã được nhận và gộp; kết quả rà soát tích hợp nằm ở `docs/INTEGRATION_REPORT.md`. Mục 0 dưới đây là phạm vi của lần rà soát ĐẦU (khi chưa có code).

## 0. Phạm vi rà soát (quan trọng)

Đã nhận: 2 file docx (kế hoạch, proposal), `member_A_handoff.md`, `rules.json`, `baseline_*.json`, `inventory.json`,
`lab_policy.json`, `expected_results.json` và 5 file `.cfg` mẫu.

**Chưa nhận: toàn bộ code Python** (`network_adapter.py`, `snapshot_collector.py`, `sanitizer.py`, `config_parser.py`,
`rule_engine.py`, `baseline.py`, `task_template.py`, `syntax_validator.py`, `verifier_and_evidence.py`, `fakes.py`, test).
Do đó **chưa thể xác nhận code chạy được trên máy thật** — chỉ có thể đánh giá dữ liệu, thiết kế và những gì handoff tự khai báo.
Phần của B (FastAPI, DB, RBAC, audit log) và C (frontend) cũng chưa được gửi nên không đánh giá được.

## 1. Những gì đã kiểm chứng được

| Kiểm tra | Kết quả |
|---|---|
| Viết lại độc lập logic 13 rule từ `rules.json`, chạy trên 5 cấu hình mẫu, so với `expected_results.json` | **65/65 cặp khớp** (33 FAIL, 32 PASS) → ground truth nhất quán với định nghĩa rule |
| Số liệu trong handoff (13 rule, 5 file, 65 cặp) | Khớp với dữ liệu thực tế |
| `lab_policy.json` ↔ `baseline_switch.json` | Nhất quán (VLAN 20 trong dải 20–29; Gi0/1 nằm trong allowed) |

Lưu ý: kết quả trên chứng minh *dữ liệu mẫu nhất quán*, **không** chứng minh `rule_engine` của A đúng, càng không chứng minh độ chính xác trên thiết bị thật.
Chạy lại bất kỳ lúc nào: `python tools/crosscheck_rules.py`.

## 2. Còn thiếu so với kế hoạch (theo tuần)

| Tuần | Yêu cầu | Tình trạng |
|---|---|---|
| 1 | Model/IOS thật của router & switch, topology, xác nhận quyền & phạm vi lab | **Thiếu.** `inventory.json` chỉ có IP/tên/role; không có model, IOS, topology. Router chưa rõ model |
| 1 | Chốt port/VLAN thử nghiệm với quản lý lab | **Chưa.** `lab_policy.json` ghi rõ là "VÍ DỤ"; `protected_interfaces` đang rỗng |
| 2 | Luồng end-to-end web/API → thiết bị | Phần A có `test_connection()` nhưng chưa chạy thiết bị thật; phần B/C chưa thấy |
| 3 | Snapshot hiển thị qua web, DB | A: xong (offline). B/C: chưa thấy |
| 4 | ≥5 rule có bằng chứng; ghi nhận cảnh báo sai | Có 13 rule (vượt yêu cầu). **Chưa đo cảnh báo sai trên cấu hình thật** — mới 5 file tự viết |
| 5 | "Xác nhận rule với thiết bị thật" (A) | **Chưa làm** (handoff tự nhận) |
| 5 | API diff/lịch sử/audit log, UI | B/C: chưa thấy |
| 6 | Một thay đổi từ web trên thiết bị thật + verify | **Chưa đạt cổng nghiệm thu tuần 6.** Template/validator/verify có nhưng chỉ chạy với `fakes.py` |
| 6 | Workflow Preview→Validate→Approve→Execute→Verify; **rollback khi verify FAIL** | Hợp đồng nêu `build_rollback_commands`, nhưng ai gọi và khi nào (tự động khi verify FAIL?) thuộc workflow của B — cần xác nhận và test |

## 3. Rủi ro khi chạy thiết bị thật (đọc từ dữ liệu có sẵn)

1. **SEC-003 (`exec-timeout`) có thể báo sai.** IOS mặc định `exec-timeout 10 0` và *không hiển thị* trong running-config.
   Rule hiện yêu cầu dòng tường minh → thiết bị để mặc định sẽ FAIL. Cần quyết định đây là "chính sách bắt buộc khai báo rõ" hay là false positive, và ghi vào mô tả rule.
2. **Gi0/1, Gi0/2 trong `lab_policy.json` có thể là uplink.** Trên nhiều Catalyst 2960 hai cổng Gi0/1–0/2 là cổng uplink. Plan cấm đụng uplink.
   Xác nhận bằng `show interfaces status` + sơ đồ lab trước khi chạy tác vụ VLAN. Nếu là uplink: đổi `allowed_interfaces` sang Fa0/x trống và đưa uplink vào `protected_interfaces`.
3. **Chưa có model thật.** `MODEL_PROFILES` chỉ có 2960; router chưa có profile. Cần chạy `show version` để biết model/IOS rồi bổ sung.
4. **Cấu hình mẫu tự viết quá sạch.** Cấu hình thật có nhiều dòng mà mẫu không có (spanning-tree, Port-channel, DHCP snooping, banner dùng ký tự phân cách khác `^C`,
   `line vty 5 15`, `ip http secure-server`…). Cần thêm ≥2 cấu hình thật đã che secret vào `sample_configs/` + `expected_results.json` (người khác ngoài A gán đáp án tay).
5. **SSH tới IOS đời cũ:** có thể lỗi thương lượng thuật toán (kex/cipher/host key). Kiểm tra bằng `ssh -v user@<ip>` trước; nếu lỗi, xử lý ở cấu hình SSH client, không sửa rule.
   Cần có user privilege 15 (hoặc enable secret), `login local`, `transport input ssh`, RSA key đủ độ dài cho SSH v2.
6. **Sanitizer:** sau khi thu snapshot thật, `grep -inE "password|secret|community|key" snapshots/*.cfg` — mọi dòng phải là `<REDACTED>` hoặc placeholder.
7. **Rollback chưa được thử** với một lần verify cố ý FAIL.

## 4. Thứ tự kiểm tra trên máy thật (chỉ-đọc trước, thay đổi sau)

1. `pip install netmiko`; điền `.env`; `python scripts/run_all_tests.py` (offline) — phải xanh trên máy của bạn.
2. `ssh -v` thử tay tới 172.16.3.121 và 172.16.3.122.
3. `NetworkAdapter(device).test_connection()` cho từng thiết bị; ghi lại model/IOS từ `show version` vào `inventory.json`/tài liệu.
4. `python scripts/snapshot_collector.py` → mở file `.cfg` kiểm tra secret (mục 3.6).
5. `python scripts/rule_engine.py <snapshot> --role switch|router`; **đối chiếu từng kết quả với `show running-config` bằng mắt** → lập bảng đúng/sai thật (đây mới là số liệu cho Tuần 8).
6. Điền đúng `lab_policy.json` (xác nhận với quản lý lab), thêm model vào `MODEL_PROFILES`.
7. Chỉ khi 1–6 ổn: chạy tác vụ VLAN trên **một** port được phép, có truy cập console dự phòng; thử cả trường hợp verify FAIL để kiểm tra rollback.
8. `python run_eval.py` (Tuần 7) không phụ thuộc thiết bị, chạy được ngay.
