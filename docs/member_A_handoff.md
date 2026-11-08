# Thành viên A — Tài liệu bàn giao Tuần 3–6

## 1. Cấu trúc

```
.env.example                      # mẫu biến môi trường (KHÔNG commit .env)
data/inventory.json              # thiết bị (có thêm trường role)
data/lab_policy.json             # VLAN/port được phép thử nghiệm  (VÍ DỤ - chỉnh theo lab)
data/rules/rules.json            # 13 rule audit (check + remediation + touch_pattern)
data/rules/baseline_*.json       # baseline switch / router
data/sample_configs/             # cấu hình đúng/sai/biên + expected_results.json (ground truth)
backend/app/devices/             # network_adapter, snapshot_collector, sanitizer, inventory_loader
backend/app/audit/               # config_parser, rule_engine
backend/app/snapshots/           # baseline (so với baseline, diff 2 snapshot)
backend/app/remediation/         # task_template, syntax_validator, verifier_and_evidence
backend/tests/unit/              # test_week3..6 (+ test_week7, test_integration_a_week7)
scripts/                         # CLI: run_all_tests, collect_snapshot, audit_config, ...
```

> Đường dẫn module trong bảng dưới là tên file gốc; sau khi gộp repo, import theo gói: `from app.devices.network_adapter import NetworkAdapter`, v.v.

| File | Vai trò |
|---|---|
| `network_adapter.py` | SSH/Netmiko: kết nối, `show version`, `show running-config`, timeout, phân loại lỗi, `apply_config`, `save_config` |
| `snapshot_collector.py` | Thu thập → làm sạch → lưu `.cfg` + `.meta.json` (chỉ lưu bản đã che bí mật) |
| `sanitizer.py` | Che password/secret/SNMP/TACACS/key; giữ loại mã hóa làm bằng chứng |
| `config_parser.py` | Tách running-config thành dòng cấp 1 + khối con; bỏ banner, timestamp |
| `rule_engine.py` | Đánh giá rule → finding theo schema chung |
| `baseline.py` | So với baseline; diff 2 snapshot, đánh dấu thay đổi liên quan bảo mật |
| `task_template.py` | Tác vụ tạo VLAN + gán port access, validate tham số, sinh rollback |
| `syntax_validator.py` | Allowlist + ngữ cảnh + phiên bản IOS + model/role + policy |
| `verifier_and_evidence.py` | Verify thật (parse `show`), evidence có cấu trúc |
| `test_week3..6.py`, `run_all_tests.py` | 69 test có `assert` |

## 2. Chạy

```bash
pip install -r backend/requirements.txt
cp .env.example .env        # điền NETSENTRY_USERNAME / PASSWORD / ENABLE_SECRET
python scripts/run_all_tests.py                      # test (không cần thiết bị thật)
python scripts/collect_snapshot.py                   # thu thập mọi thiết bị trong inventory
python scripts/collect_snapshot.py --device Switch-LAB
python scripts/collect_snapshot.py --device Switch-LAB --from-file cfg.txt   # offline
python scripts/audit_config.py data/sample_configs/switch_bad.cfg --role switch
```

## 3. Đối chiếu yêu cầu của kế hoạch

| Tuần | Yêu cầu A | Đáp ứng bởi |
|---|---|---|
| 3 | Hoàn thiện thu thập snapshot; lưu raw output an toàn | `network_adapter`, `snapshot_collector`, `sanitizer` |
| 4 | Rule audit dựa trên bằng chứng; cấu hình đúng/sai có kiểm soát; chỉ rule phù hợp thiết bị | `rules.json`, `rule_engine`, `sample_configs/` (`applies_to`, `NOT_APPLICABLE`) |
| 5 | Baseline + cách so sánh | `baseline_*.json`, `baseline.py` |
| 6 | Template + kiểm tra cú pháp theo model/IOS + bước verify | `task_template`, `syntax_validator`, `verifier_and_evidence` |

## 4. Hợp đồng cho B (không cần đổi schema backend)

```python
# Thu thập
collect_snapshot(device, out_dir=None) -> {"ok": True, "snapshot": meta} | {"ok": False, "error_type", "message"}
NetworkAdapter(device).test_connection() -> {"ok","error_type","message","latency_ms","prompt"}   # không raise

# Audit
evaluate_config(config_text, device, rules=None) -> [finding]
finding = {rule_id, device_id, device_name, title, severity, status, evidence[list], rationale, remediation[list], checked_at}
status ∈ PASS | FAIL | NOT_APPLICABLE | ERROR      # B chỉ cần lưu FAIL vào bảng findings

# Baseline / diff
compare_to_baseline(config_text, load_baseline("switch")) -> {"compliant", "drifts": [...]}
diff_configs(old_text, new_text, rules) -> {"changed", "summary", "changes": [{section, change, line, security_relevant, related_rules}]}

# Remediation (thứ tự B nên gọi)
task = build_vlan_task(vlan_id, name, iface)                         # PREVIEW  (raise TaskValidationError nếu tham số sai)
validate_ios_syntax(task["config_commands"], ios_version, model=..., device_role=..., policy=...)   # VALIDATE
# (người dùng APPROVE)
rollback = build_rollback_commands(task["params"], pre_if_output, vlan_existed)   # trước khi EXECUTE
adapter.apply_config(task["config_commands"])                        # EXECUTE -> {"ok","output","errors"}
verify_vlan(adapter.run_show, vlan_id, name, iface)                  # VERIFY  -> PASS/FAIL/ERROR
adapter.save_config()                                                # chỉ lưu SAU KHI verify PASS
generate_task_evidence(...); save_evidence(ev)
```

Lỗi kết nối: `error_type` ∈ `TIMEOUT | AUTH | CONNECTION | COMMAND | CONFIG | UNKNOWN`.

## 5. Lệnh sử dụng

**Chỉ đọc** (`run_show` chặn mọi thứ không phải `show ...`): `show version`, `show running-config`,
`show running-config interface <if>`, `show vlan brief`, `show interfaces <if> switchport`.

**Cấu hình** (chỉ `apply_config`, sau approve): `vlan N`, `name X`, `exit`, `interface <Fa|Gi>x/y`,
`switchport mode access`, `switchport access vlan N`, `no shutdown`. Rollback thêm `default interface`, `no vlan N`.

## 6. Giới hạn đã biết

- **Chưa chạy trên thiết bị thật.** Toàn bộ test dùng thiết bị giả (`fakes.py`) với output mô phỏng IOS 15.x. Khi có lab cần kiểm tra:
  1. `parse_show_version` đọc đúng model/IOS/serial của switch và router thật.
  2. `show running-config interface X` và `default interface X` chạy được trên IOS của lab.
  3. Cách IOS hiển thị `no ip domain lookup` / `no ip domain-lookup` (rule chấp nhận cả hai).
  4. Điền `lab_policy.json` đúng VLAN/port được phép, và thêm model thật vào `MODEL_PROFILES` (hiện chỉ có 2960).
- Precision/recall = 1.00 chỉ trên bộ mẫu tự viết (5 file, 65 cặp cấu hình–rule). Đây KHÔNG phải độ chính xác trên thiết bị thật; cần thêm cấu hình thật (đã bỏ secret) vào `sample_configs/` và `expected_results.json`.
- Snapshot đã che mật khẩu nên **đổi mật khẩu không hiện trong diff**. Rule SEC-012 chỉ kết luận về community mặc định `public/private`, không đánh giá độ mạnh của community khác.
- Rule dựa trên pattern dòng lệnh; không hiểu ngữ nghĩa ACL hay thứ tự lệnh.
- `interface` hỗ trợ cho tác vụ VLAN: FastEthernet/GigabitEthernet (không cho TenGigabit/uplink).
