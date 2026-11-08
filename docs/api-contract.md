# API Contract (PROPOSAL by Member C — Backend/B owns the final version)

Derived from plan §5.1 plus endpoints the UI needs (marked ★). Frontend client: `frontend/src/api/client.ts`. Types: `frontend/src/types/index.ts`.
All responses are JSON. Errors: HTTP 4xx/5xx with `{"detail": "<human readable message>"}` (the UI shows `detail` verbatim — never put secrets or stack traces in it).

| Method & path | Purpose | Success | Notable errors |
|---|---|---|---|
| GET `/api/devices` | List devices | `Device[]` | |
| ★ GET `/api/devices/{id}` | One device | `Device` | 404 |
| POST `/api/devices/{id}/test-connection` | Test SSH; updates `connection_status`/`last_error` | `Device` | 404; connection failures should be returned as 200 with `connection_status=unreachable` + `last_error` |
| POST `/api/devices/{id}/scans` | Run audit | `ScanRun` | 404, 409 if a scan is running |
| ★ GET `/api/devices/{id}/scans`, ★ GET `/api/scans` | Scan history | `ScanRun[]` | |
| GET `/api/scans/{id}/findings` | Findings of a scan | `Finding[]` | 404 |
| ★ GET `/api/devices/{id}/findings`, ★ GET `/api/findings` | Findings (latest per rule) | `Finding[]` | |
| POST `/api/devices/{id}/snapshots` | Take snapshot | `ConfigSnapshot` | 404, 502 device error |
| ★ GET `/api/devices/{id}/snapshots` | List snapshots (newest first) | `ConfigSnapshot[]` | |
| GET `/api/devices/{id}/diff?from=&to=` | Diff two snapshots | `SnapshotDiff` | 404 |
| ★ GET `/api/audit-logs` | Audit log (newest first) | `AuditLogEntry[]` | 403 for roles without access |
| POST `/api/remediations/preview` | Body `{action_type,target_device,params}` → job with `preview` (from template) and `validation_errors` | `RemediationJob` | 400 action not in allowlist |
| POST `/api/remediations/{id}/approve` | Approve | `RemediationJob` | 409 if validation errors; 403 RBAC |
| ★ POST `/api/remediations/{id}/reject` | Reject | `RemediationJob` | |
| POST `/api/remediations/{id}/execute` | Execute approved job | `RemediationJob` | 409 if not approved; 403 RBAC |
| GET `/api/remediations/{id}/verify` | Verify post-change state | `RemediationJob` (with `verification_result`) | 409 if not executed |
| POST `/api/assistant/explain` | **Implemented** in `backend/app/assistant/router.py`. Body `{finding, question?}` | `ExplainResponse` | 422 invalid body |

## Rules the UI relies on
1. **Preview text comes from the server's template**, never from user free text. The UI shows `preview[]` exactly.
2. Server must enforce state machine: `approve` only when `validation_errors` empty; `execute` only when `approval_status=approved`; `verify` only after `execution_status=succeeded`. UI also disables buttons, but the server is authoritative (UI mock mirrors these rules).
3. Server must block uplinks and non-allowlisted actions regardless of UI.
4. `ConfigSnapshot.content` must already be secret-masked.
5. Timestamps ISO-8601 UTC.

## Assistant schema (owned by C)
Request: `{"finding": {rule_id,title,severity,evidence[],rationale,remediation,...}, "question": "optional, ≤500 chars"}`
Response: `{"provider": str, "explanation": {summary, why_it_matters, evidence_refs[], suggested_action: "create_vlan"|"configure_access_port"|null, suggested_params{}, confidence: low|medium|high, caveats[]} | null, "rejected_reason": str | null}`
Exactly one of `explanation` / `rejected_reason` is non-null. `suggested_action` is a hint only; to act on it the user must create a normal remediation preview.
