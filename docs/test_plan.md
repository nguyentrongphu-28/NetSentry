# Kế Hoạch Kiểm Thử NetSentry (Test Plan)

Tài liệu xác định phạm vi, môi trường, các cấp độ kiểm thử, chiến lược kiểm thử tự động, tiêu chí nghiệm thu và công cụ thực thi cho toàn bộ hệ thống NetSentry.

---

## 1. Mục Tiêu & Phạm Vi Kiểm Thử (Scope & Objectives)

- **Mục tiêu**: Đảm bảo 100% tính năng lõi (Kiểm toán CIS, RBAC, Snapshot/Diff, Baseline/Drift, AI Explanation, Remediation Plan & Execution) hoạt động chính xác, bảo mật và ổn định.
- **Phạm vi kiểm thử**:
  1. *Cấp 1 - Kiểm thử đơn vị & Thuật toán lõi (Unit Tests)*: Domain entities, state machines, password hashing, config redaction, rule parsing AST, confusion matrix metrics calculation.
  2. *Cấp 2 - Kiểm thử tích hợp API & Bảo mật (API & Security Tests)*: Ma trận RBAC (viewer/operator/admin), CSRF origin check, bảo vệ brute-force, path traversal/SSRF, prompt injection.
  3. *Cấp 3 - Kiểm thử dòng chảy đầu-cuối (End-to-End API Workflows)*: Kịch bản tuần tự hoàn chỉnh (Audit -> Propose -> Approve -> Apply -> Verify -> Diff compare) với mock connectors.
  4. *Cấp 4 - Đánh giá độ chính xác (Corpus Evaluation)*: Đánh giá rule engine trên tập cấu hình độc lập đóng băng (`MANIFEST.sha256`).
  5. *Cấp 5 - Giao diện người dùng (Frontend Unit & Component Tests)*: Vitest + React Testing Library + MSW.

---

## 2. Ma Trận Chiến Lược Kiểm Thử (Test Strategy Matrix)

| Cấp độ | Công cụ / Framework | Đường dẫn kiểm thử chính | Tần suất thực thi | Tiêu chí đạt |
| :--- | :--- | :--- | :--- | :--- |
| **Đơn vị (Unit)** | Pytest | `backend/tests/unit/` | Mỗi lần commit / verify_all | 100% pass |
| **API & RBAC** | Pytest + Starlette TestClient | `backend/tests/api/` | Mỗi lần commit / verify_all | 100% pass |
| **Đầu-cuối (E2E API)** | Pytest + TestClient + Fakes | `backend/tests/e2e/test_full_workflow.py` | CI / Pre-release | 5/5 kịch bản pass |
| **Bảo mật (S1-S15)** | `evaluation/security_matrix.py` | `evaluation/security_matrix.yaml` | Pre-release | 47/47 node pass, 0 GAP |
| **Độ chính xác Rule** | `evaluation/rule_eval.py` | `evaluation/corpus/` | Pre-release | F1 $\ge$ 95%, 0 rò rỉ |
| **Kháng Injection AI** | `evaluation/ai_eval.py` | `evaluation/ai/injection_cases.json` | Pre-release | 20/20 ca an toàn |
| **Giao diện Frontend** | Vitest + ESLint + TypeScript | `frontend/` | Mỗi lần build | Lint 0 err, Typecheck OK |

---

## 3. Môi Trường & Dữ Liệu Kiểm Thử (Test Environments & Data)

- **Môi trường cục bộ**: Python 3.12 (venv với exact 50 packages), Node.js v20+, SQLite in-memory / tmp_path.
- **Dữ liệu giả lập (Fixtures)**:
  - Cấu hình Cisco IOS chuẩn: `ios_secure.cfg`, `ios_insecure.cfg`, `ios_minimal.cfg`, `ios_banner_trap.cfg`.
  - Corpus kiểm toán: 8 cấu hình độc lập (`configs/dev/`, `configs/test/`) kèm nhãn `labels.json`.
  - Bộ ca tấn công Injection: 20 trường hợp trong `injection_cases.json`.
- **Môi trường Lab thực tế (Tùy chọn cho người vận hành)**:
  - Router Cisco thật (ví dụ Cisco 2911 / 1941 hoặc mô phỏng PNETLab/GNS3) để đo thời gian mạng và chu trình áp dụng lệnh cấu hình.

---

## 4. Tiêu Chí Nghiệm Thu (Acceptance Criteria)

1. **Chức năng kiểm toán**: Đánh giá đúng 8/8 rule CIS Benchmark; phát hiện chính xác các vi phạm `FAIL`, `UNKNOWN`, `PASS`.
2. **Kiểm soát bảo mật 4 mắt (Four-Eyes)**: Không cho phép tự phê duyệt bản vá; bắt buộc xác thực lại mật khẩu; phát hiện sai lệch băm `PLAN_HASH_MISMATCH`.
3. **An toàn hoàn tác**: Tự động đảo ngược cấu hình nếu xác minh sau khi sửa không đạt yêu cầu an toàn.
4. **Không rò rỉ thông tin**: Tuyệt đối không để lộ mật khẩu, enable secret hay token trong database, nhật ký hay API response.
5. **Hiệu năng & Khả năng tái lập**: Scripts chạy từ môi trường máy sạch thông qua lệnh duy nhất `bash scripts/verify_all.sh` mà không phát sinh lỗi.
