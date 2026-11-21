# Ma Trận Truy Vết Yêu Cầu Dự Án (Traceability Matrix)

Tài liệu ánh xạ chi tiết giữa **Mục tiêu / Đề xuất đồ án** và **Tiêu chí nghiệm thu kế hoạch 8 tuần** với tính năng triển khai thực tế và bằng chứng kiểm thử (test nodes, scripts, tài liệu).

---

## 1. Bảng Truy Vết Yêu Cầu Chức Năng & Nghiệm Thu (Requirement Traceability)

| Mã | Mục tiêu / Yêu cầu trong Đề xuất | Tính năng triển khai thực tế trong NetSentry | Bằng chứng kiểm thử / Đường dẫn mã nguồn | Trạng thái |
| :---: | :--- | :--- | :--- | :---: |
| **REQ-01** | Thu thập cấu hình thiết bị tự động qua SSH an toàn | Connector `CiscoIOSConnector` & `FakeConnector` chỉ đọc với cơ chế Allowlist lệnh nghiêm ngặt | [test_cisco_ios_connector.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/unit/connectors/test_cisco_ios_connector.py) | **ĐẠT** |
| **REQ-02** | Kiểm toán tuân thủ 8 quy tắc CIS Cisco IOS Benchmark | `RuleEngine` độc lập, không mạng, phân tích AST cấu hình với 8 rule NET-001..NET-008 | [rule_eval.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/evaluation/rule_eval.py), [test_evaluation_corpus.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/unit/test_evaluation_corpus.py) | **ĐẠT** |
| **REQ-03** | Xác thực người dùng và phân quyền RBAC đa vai trò | `AuthService` với Argon2id, Session HTTP-only cookie, 3 vai trò Viewer / Operator / Admin | [test_rbac_matrix.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/api/test_rbac_matrix.py), [test_auth_routes.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/api/test_auth_routes.py) | **ĐẠT** |
| **REQ-04** | Quản lý phiên bản snapshot và phát hiện sai lệch (Diff / Drift) | `SnapshotService` che HMAC secret, `DiffService` tính khác biệt, `BaselineService` quản lý mốc chuẩn | [test_snapshots_api.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/api/test_snapshots_api.py), [test_baselines_api.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/api/test_baselines_api.py) | **ĐẠT** |
| **REQ-05** | Hỗ trợ AI giải thích rủi ro và khuyến nghị an ninh | `AiExplainService` kết nối Ollama LLM cục bộ, qua bộ lọc `ExplanationValidator` làm sạch | [test_llm_layer.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/unit/test_llm_layer.py), [ai_eval.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/evaluation/ai_eval.py) | **ĐẠT** |
| **REQ-06** | Đề xuất khắc phục và quy trình phê duyệt 4 mắt (Four-Eyes) | `RemediationService` quản lý vòng đời kế hoạch, chặn tự duyệt, bắt buộc step-up password | [test_remediation_service.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/unit/test_remediation_service.py), [test_remediation_api.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/api/test_remediation_api.py) | **ĐẠT** |
| **REQ-07** | Thực thi bản vá an toàn với cơ chế xác minh và hoàn tác tự động | `RemediationExecutor` nền, hỗ trợ Dry-Run / Live, kiểm tra verification audit, rollback khi thất bại | [test_remediation_executor.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/unit/test_remediation_executor.py), [test_full_workflow.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/e2e/test_full_workflow.py) | **ĐẠT** |
| **REQ-08** | Giao diện web trực quan, responsive và có thông báo rõ ràng | Frontend React 19 + TypeScript + TailwindCSS, hỗ trợ toast, modal xác nhận, badge trạng thái | [frontend test](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/frontend) (Vitest unit tests) | **ĐẠT** |
| **REQ-09** | Báo cáo kiểm toán & nhật ký truy vết bảo mật | Lưu vết mọi thay đổi nhạy cảm trong bảng `security_events` và `remediation_events` không rò rỉ secret | [test_users_events_api.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/api/test_users_events_api.py), [test_leak_prevention.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/unit/test_leak_prevention.py) | **ĐẠT** |
| **REQ-10** | Đảm bảo tính an toàn trong môi trường demo công khai | Chế độ `NETSENTRY_PUBLIC_MODE=1` khóa tài liệu API, cấm tắt auth, chặn truy xuất config thô | [test_config_middleware.py](file:///home/trongphu/Learning/Q1_26-27/CSN301/Project/NetSentrySelf/backend/tests/unit/test_config_middleware.py) | **ĐẠT** |

---

## 2. Ghi Chú Thiết Kế: Thay Đổi So Với Ý Tưởng Sơ Khai

- **Sinh lệnh sửa đổi (Remediation CLI Generation)**:
  - *Ý tưởng sơ đồ ban đầu trong đề cương*: Để AI tự do sinh cấu hình CLI tương ứng với lỗ hổng.
  - *Hiện thực hóa bảo mật chuẩn*: Để ngăn chặn nguy cơ **Prompt Injection gián tiếp** (kẻ tấn công chèn lệnh độc hại vào hostname, banner hoặc description trên router khiến AI sinh lệnh phá hoại), hệ thống đã chuyển sang kiến trúc: **AI chỉ giải thích ngữ cảnh và rủi ro; lệnh sửa đổi bắt buộc tuân theo Template CLI tĩnh đã kiểm chứng và kiểm tra Allowlist**.
  - Thiết kế này tuân thủ các chuẩn an ninh khắt khe nhất (NIST AI Risk Management Framework & OWASP Top 10 for LLM Applications).
