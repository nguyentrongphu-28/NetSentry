# API contract — AI assistant (Tuần 7)

Module nằm sẵn ở `backend/app/assistant/`; dùng chung `data/rules/rules.json` và `data/lab_policy.json` với module của A.

## Khởi tạo (một lần khi backend khởi động)

```python
import json
from app.assistant import AssistantService, load_policy, make_client_from_env

from app.audit.rule_engine import load_rules
from app.core.paths import POLICY_PATH

rules = load_rules()                      # data/rules/rules.json
assistant = AssistantService(make_client_from_env(), rules, load_policy(POLICY_PATH))
```

Biến môi trường: `NETSENTRY_AI_PROVIDER` (`openai`|`gemini`), `NETSENTRY_AI_MODEL` (tên model, **không có mặc định**),
`OPENAI_API_KEY` hoặc `GEMINI_API_KEY`, `NETSENTRY_AI_TIMEOUT` (giây, mặc định 30). Khóa API chỉ nằm ở `.env` (gốc repo, được `make_client_from_env()` tự nạp).

## Endpoint

| Endpoint | Body | Gọi |
|---|---|---|
| `POST /api/assistant/explain` | `{"finding_id": int, "language": "vi"\|"en"}` | `assistant.explain_finding(finding_dict, language)` |
| `POST /api/assistant/chat` | `{"message": str, "finding_ids": [int], "language": "vi"\|"en"}` | `assistant.chat(message, [finding_dict...], language)` |

`finding_dict` = đúng schema finding của A: `{rule_id, device_id, device_name, title, severity, status, evidence[list[str]], rationale, remediation[list], checked_at}`.
**B lấy finding từ DB theo id** — không nhận nội dung finding do client gửi lên.

## Phản hồi

```jsonc
{ "ok": true,
  "source": "llm" | "fallback" | "deterministic" | "gate",
  "reply": { "answer", "why_it_matters", "evidence_used": [{"rule_id","quote"}], "risk_level",
             "impact_of_fix", "manual_steps": [str], "proposed_action": null | {"action_type":"create_vlan_assign_access_port",
             "params":{"vlan_id","name","interface"}, "requires_approval": true},
             "confidence", "insufficient_data", "injection_noticed" },
  "warnings": [str], "attempts": int,
  "audit_events": [{"event","ts","detail"}] }
```
Lỗi nghiệp vụ: `{"ok": false, "source": "gate"|"policy", "error"|"blocked", "message", "errors"|"reason_codes", "audit_events"}`.
Gợi ý mã HTTP: `200` cho `ok:true` (kể cả `source:"fallback"`); `422` cho `source:"policy"` hoặc `blocked:true`; `404` finding không tồn tại; `401/403` RBAC.

## Bắt buộc phía backend

1. **Lưu `audit_events`** vào bảng `audit_logs` cùng user_id, thời gian, finding_id (mỗi lần gọi, kể cả bị chặn).
2. **`proposed_action` chỉ là đề xuất.** `action_type` trùng `task_template.ACTION_TYPE` của A; khóa `params` của AI là `{vlan_id, name, interface}` → B ánh xạ sang `build_vlan_task(vlan_id, vlan_name=name, interface_name=interface)`. Chuyển sang `POST /api/remediations/preview` và **validate lại hoàn toàn** bằng `validate_ios_syntax` + `lab_policy` của A. Không tin kết quả của AI.
   Không có endpoint nào cho AI tự `execute`; `approve` yêu cầu người dùng có role phù hợp.
3. `manual_steps` chỉ để hiển thị. Không đưa vào `apply_config`.
4. RBAC: cần đăng nhập; giới hạn tốc độ (vd. 10 lượt/phút/user); timeout HTTP > `NETSENTRY_AI_TIMEOUT`.
5. Không log nguyên văn đầu ra LLM bị từ chối (service chỉ ghi mã lỗi + hash 16 ký tự).

## Bắt buộc phía frontend (C)

* Hiển thị `answer`, `manual_steps`… như **văn bản thuần** (không render Markdown/HTML) — validator đã chặn URL/ảnh nhưng đây là lớp thứ hai.
* Nếu `warnings` có `injection_suspected_in_evidence:*` hoặc `reply.injection_noticed` → hiện cảnh báo "bằng chứng có chứa nội dung giống chỉ dẫn".
* Nếu `source` là `fallback` → ghi nhãn "giải thích dự phòng (không do AI)".
* Nút "Tạo thay đổi" chỉ chuyển sang màn hình Preview; không có nút "áp dụng ngay" trong khung chat.

## Phác thảo FastAPI (chưa chạy thử — môi trường dựng module không có FastAPI)

```python
@router.post("/api/assistant/explain")
def explain(body: ExplainIn, user=Depends(require_role("analyst"))):
    finding = db.get_finding(body.finding_id) or raise_404()
    result = assistant.explain_finding(finding, body.language)
    audit.write_many(user.id, result["audit_events"])
    return JSONResponse(result, status_code=200 if result["ok"] else 422)
```
