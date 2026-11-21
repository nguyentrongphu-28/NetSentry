# Kiến Trúc Hệ Thống NetSentry (Architecture Overview)

Tài liệu mô tả chi tiết kiến trúc tổng thể, ranh giới tin cậy (trust boundaries), luồng tuần tự xử lý kiểm toán (Audit), luồng đề xuất và áp dụng bản vá (Remediation C/D), máy trạng thái kế hoạch sửa đổi và mô hình dữ liệu (ERD).

---

## 1. Sơ Đồ Thành Phần & Ranh Giới Tin Cậy (System Context & Trust Boundaries)

Hệ thống tuân thủ nghiêm ngặt mô hình phòng thủ theo chiều sâu (Defense-in-Depth) với 4 ranh giới bảo mật riêng biệt:

```mermaid
flowchart TB
    subgraph UntrustedZone["1. Môi trường Bên ngoài / Trình duyệt (Untrusted)"]
        UserBrowser["Web Browser (React 19 / Vite SPA)"]
        CloudflareEdge["Cloudflare Quick Tunnel (TLS Termination)"]
    end

    subgraph AppBoundary["2. Vùng Ứng dụng Backend NetSentry (Trusted App Boundary)"]
        direction TB
        ReverseProxy["Origin / Host & Security Headers Middleware"]
        AuthModule["Auth & RBAC Service (Argon2id + HTTP-only Cookie)"]
        AuditEngine["CIS Rule Engine (In-Memory Offline AST Parser)"]
        SnapshotService["Snapshot & Redactor (HMAC-SHA256 Masking)"]
        RemediationModule["Remediation Engine & State Machine"]
        DB[(SQLite Embedded DB)]
    end

    subgraph InternalServices["3. Vùng Dịch vụ Nội bộ (Internal Subnet / Localhost)"]
        OllamaLocal["Ollama LLM Instance (Qwen 2.5 / Port 11434)"]
    end

    subgraph NetworkDevices["4. Vùng Thiết bị Mạng Cốt lõi (Management Network)"]
        CiscoRouter["Cisco IOS Router / Switch"]
    end

    UserBrowser -->|HTTPS / WSS| CloudflareEdge
    CloudflareEdge -->|Reverse Proxy Tunnel| ReverseProxy
    ReverseProxy --> AuthModule
    AuthModule --> AuditEngine
    AuthModule --> RemediationModule
    AuditEngine --> SnapshotService
    SnapshotService --> DB
    RemediationModule --> DB

    AuditEngine -.->|JSON Prompt / Sanitized Findings| OllamaLocal
    OllamaLocal -.->|Natural Explanation Only| AuditEngine

    AuditEngine -->|SSH Read-Only / Allowlisted 'show'| CiscoRouter
    RemediationModule -->|Dedicated Write SSH Session / Allowlisted Templates| CiscoRouter
```

---

## 2. Luồng Tuần Tự Kiểm Toán Thiết Bị (Audit Sequence)

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Operator (Quản trị viên vận hành)
    participant API as NetSentry REST API
    participant Conn as CiscoIOSConnector (Read-Only)
    participant Redactor as ConfigRedactor
    participant Engine as RuleEngine (8 CIS Rules)
    participant DB as SQLite DB
    participant AI as AiExplainService (Ollama)

    Operator->>API: POST /api/v1/devices/{id}/audit
    API->>Conn: connect() & get_running_config()
    Note over Conn: Chỉ thực thi lệnh show trong allowlist.<br/>Mọi lệnh cấu hình bị từ chối tuyệt đối.
    Conn-->>API: raw_config_text
    API->>Redactor: redact(raw_config_text)
    Redactor-->>API: sanitized_config (Secrets replaced with HMAC markers)
    API->>Engine: run(raw_config_text)
    Engine-->>API: findings [NET-001 .. NET-008]
    API->>DB: Lưu audit_runs, findings, snapshots
    API-->>Operator: 201 Created (AuditSummary + Findings)

    opt Người dùng yêu cầu giải thích AI
        Operator->>API: POST /api/v1/audits/{id}/explain
        API->>AI: generate_explanation(findings, evidence)
        Note over AI: LLM chỉ giải thích rủi ro.<br/>Không bao giờ sinh lệnh sửa đổi CLI.
        AI-->>API: validated_explanation
        API-->>Operator: 200 OK (AI Explanation JSON)
    end
```

---

## 3. Luồng Tuần Tự Khắc Phục Lỗi Cấu Hình (Remediation Lifecycle)

NetSentry áp dụng nguyên tắc kiểm soát 4 mắt (Four-Eyes Principle / Maker-Checker): người đề xuất không được tự phê duyệt; lệnh thực thi bắt buộc khớp mẫu tĩnh đã kiểm chứng.

```mermaid
sequenceDiagram
    autonumber
    actor Proposer as Operator / Admin (Proposer)
    actor Approver as Distinct Admin (Approver)
    participant API as Remediation API
    participant Engine as RemediationService
    participant Executor as RemediationExecutor (Background Worker)
    participant Writer as CiscoIOSConfigWriter
    participant Device as Cisco IOS Router

    Proposer->>API: POST /audits/{id}/findings/{rule}/remediation
    API->>Engine: propose(rule_id, finding)
    Note over Engine: Chỉ rule hợp lệ (NET-004, NET-008) & finding FAIL.<br/>Lệnh sinh từ template tĩnh; tính plan_hash.
    Engine-->>API: Plan #1 (PROPOSED)
    API-->>Proposer: 201 Created

    Approver->>API: POST /remediation-plans/{id}/approve (Password)
    Note over Approver: Xác thực lại mật khẩu (Step-up Auth).<br/>Chặn tự duyệt nếu Proposer == Approver.
    API->>Engine: approve(plan_id, approver, password)
    Engine-->>API: Plan #1 (APPROVED)
    API-->>Approver: 200 OK

    Approver->>API: POST /remediation-plans/{id}/apply (Confirm Device + Password)
    API->>Engine: apply(plan_id, confirm_device_id)
    Note over Engine: CAS Atomic Lock trên thiết bị.<br/>Kiểm tra tính toàn vẹn plan_hash.
    Engine->>Executor: execute_async(plan_id)
    Engine-->>Approver: 202 Accepted (Execution #101 RUNNING)

    rect rgb(240, 248, 255)
        Note over Executor,Device: Tiến trình thực thi ngầm độc lập (Background Job)
        Executor->>Writer: apply(commands)
        Writer->>Device: Gửi lệnh cấu hình qua SSH phiên ghi riêng
        Executor->>API: Chạy Verification Audit độc lập
        alt Verification PASS
            Executor->>Writer: save_config() -> "write memory"
            Executor-->>API: Đánh dấu Plan VERIFIED
        else Verification FAIL
            Executor->>Writer: apply(rollback_commands, is_rollback=True)
            Executor-->>API: Đánh dấu Plan ROLLED_BACK
        end
    end
```

---

## 4. Máy Trạng Thái Kế Hoạch Khắc Phục (Plan State Machine)

```mermaid
stateDiagram-v2
    [*] --> PROPOSED: Propose (Finding FAIL)
    
    PROPOSED --> APPROVED: Distinct Admin Approve (Step-up Auth)
    PROPOSED --> REJECTED: Admin Reject
    PROPOSED --> CANCELLED: Proposer / Admin Cancel
    PROPOSED --> EXPIRED: TTL Quá hạn (1440m)

    APPROVED --> APPLYING: Admin Apply (Live Mode CAS Lock)
    APPROVED --> EXPIRED: TTL Quá hạn (120m)
    APPROVED --> CANCELLED: Admin Cancel
    APPROVED --> APPROVED: Dry-Run Apply (Thử nghiệm mô phỏng)

    APPLYING --> APPLIED: Config Writer áp dụng thành công
    APPLYING --> FAILED: SSH Lỗi / Lệnh bị từ chối

    APPLIED --> VERIFIED: Verification Audit PASS (write memory)
    APPLIED --> ROLLED_BACK: Verification Audit FAIL (Rollback OK)
    APPLIED --> VERIFY_FAILED: Không hoàn tác được (Cần can thiệp)
    APPLIED --> FAILED: Lỗi hệ thống bất ngờ

    VERIFIED --> [*]
    ROLLED_BACK --> [*]
    VERIFY_FAILED --> [*]
    FAILED --> [*]
    REJECTED --> [*]
    CANCELLED --> [*]
    EXPIRED --> [*]
```

---

## 5. Mô Hình Thực Thể Dữ Liệu (Entity-Relationship Diagram)

```mermaid
erDiagram
    USERS ||--o{ SESSIONS : has
    USERS ||--o{ SECURITY_EVENTS : triggers
    USERS ||--o{ REMEDIATION_PLANS : proposes
    USERS ||--o{ REMEDIATION_PLANS : decides

    DEVICES ||--o{ AUDIT_RUNS : targets
    DEVICES ||--o{ SNAPSHOTS : owns
    DEVICES ||--o{ BASELINES : establishes
    DEVICES ||--o{ REMEDIATION_PLANS : targets

    AUDIT_RUNS ||--o{ FINDINGS : contains
    AUDIT_RUNS ||--o| SNAPSHOTS : captures
    AUDIT_RUNS ||--o| AI_EXPLANATIONS : explains
    AUDIT_RUNS ||--o{ DRIFT_REPORTS : evaluated_in

    REMEDIATION_PLANS ||--o{ REMEDIATION_EXECUTIONS : executes
    REMEDIATION_PLANS ||--o{ REMEDIATION_EVENTS : logs

    USERS {
        int id PK
        string username UK
        string password_hash
        string role
        boolean is_active
        boolean must_change_password
        int failed_logins
        datetime locked_until
    }

    DEVICES {
        string device_id PK
        string name
        string host
        int port
        string platform
        datetime created_at
        datetime updated_at
    }

    AUDIT_RUNS {
        int id PK
        string device_id FK
        string status
        datetime started_at
        datetime finished_at
        int pass_count
        int fail_count
        int unknown_count
        string error_code
    }

    FINDINGS {
        int id PK
        int audit_run_id FK
        string rule_id
        string title
        string severity
        string status
        text evidence_json
    }

    REMEDIATION_PLANS {
        int id PK
        string device_id FK
        int run_id FK
        string rule_id
        string status
        string risk_level
        boolean persist_after_verify
        text commands_json
        string plan_hash
        string proposed_by
        string decided_by
        datetime expires_at
    }

    REMEDIATION_EXECUTIONS {
        int id PK
        int plan_id FK
        string mode
        datetime started_at
        datetime finished_at
        string result
        string failure_code
        boolean changes_sent
        string persist_status
        boolean needs_manual_attention
    }
```
