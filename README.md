# NetSentry AI

Nền tảng đánh giá cấu hình bảo mật Cisco và hỗ trợ khắc phục có AI (đồ án CSN301 — EIU).
Luồng: kết nối SSH chỉ-đọc → snapshot (đã che bí mật) → rule audit có bằng chứng → baseline/diff → remediation có kiểm soát
(Preview → Validate → Approve → Execute → Verify) → AI giải thích/đề xuất (không bao giờ tự thực thi).

## Cấu trúc

```
.env.example   .gitignore   README.md
backend/
  app/
    core/          paths.py, env.py              # đường dẫn, nạp .env
    devices/       network_adapter, snapshot_collector, sanitizer, inventory_loader   (A)
    audit/         config_parser, rule_engine                                          (A)
    snapshots/     baseline (so baseline, diff 2 snapshot)                             (A)
    remediation/   task_template, syntax_validator, verifier_and_evidence              (A)
    assistant/     AI: guards, policy_gate, validator, prompts, llm_client, service    (tuần 7)
    api/ db/       (chưa có — B: FastAPI, DB, RBAC)
  tests/unit/      test_week3..7 + test_integration_a_week7
  tests/lab/       (test trên thiết bị thật — bổ sung ở tuần 8)
  requirements.txt
data/
  inventory.json  lab_policy.json  standard_questions.json
  rules/           rules.json, baseline_switch.json, baseline_router.json
  sample_configs/  *.cfg + expected_results.json (ground truth)
  snapshots/ reports/   # sinh ra khi chạy, không commit
docs/              handoff của A, API contract AI, báo cáo tuần 7, INTEGRATION_REPORT.md
frontend/          (chưa có — C)
scripts/           run_all_tests.py  collect_snapshot.py  audit_config.py  run_ai_eval.py  crosscheck_rules.py
```

## Chạy nhanh (không cần thiết bị, mạng hay API key)

```bash
python -m venv .myvenv && source .myvenv/bin/activate     # Windows: .myvenv\Scripts\activate
pip install -r backend/requirements.txt                    # chỉ cần netmiko khi nối thiết bị thật
python scripts/run_all_tests.py                            # 134 test
python scripts/audit_config.py data/sample_configs/switch_bad.cfg --role switch
python scripts/run_ai_eval.py                              # bảng kết quả an toàn của AI (offline, MockLLM)
python scripts/crosscheck_rules.py                         # đối chiếu độc lập rules.json <-> expected_results.json
```

Thiết bị thật: `cp .env.example .env`, điền tài khoản, rồi `python scripts/collect_snapshot.py --device <tên>`.
AI thật: đặt `NETSENTRY_AI_PROVIDER`, `NETSENTRY_AI_MODEL` và khóa API trong `.env`, rồi `python scripts/run_ai_eval.py --live`.

## Quy tắc an toàn
* Chỉ kết nối thiết bị được phép; `run_show` chỉ nhận lệnh `show`; thay đổi chỉ qua template + allowlist + phê duyệt.
* AI không có SSH/tool; đầu ra qua validator; `proposed_action` chỉ là đề xuất, backend validate lại hoàn toàn.
* Không commit `.env`, mật khẩu, snapshot, cấu hình thật. `.myvenv/` đã nằm trong `.gitignore`.

## Trạng thái / giới hạn
Xem `docs/INTEGRATION_REPORT.md` (mục 4) và `docs/member_A_handoff.md` (mục 6).
