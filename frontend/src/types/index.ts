// Types mirror the standardized schemas in the implementation plan (section 3).
// Source of truth for the API is backend (member B). See docs/api-contract.md.

export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type FindingStatus = "open" | "resolved" | "accepted" | "false_positive";
export type ConnectionStatus = "reachable" | "unreachable" | "unknown";

export interface Device {
  device_id: string;
  hostname: string;
  ip_address: string;
  role: "switch" | "router";
  model: string;
  ios_version: string;
  connection_status: ConnectionStatus;
  last_scan_at: string | null;
  last_error: string | null;
}

export interface ScanRun {
  scan_id: string;
  device_id: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "completed" | "failed";
  duration_seconds: number | null;
  findings_count: number;
  error: string | null;
}

export interface Finding {
  rule_id: string;
  device_id: string;
  scan_id: string;
  title: string;
  severity: Severity;
  evidence: string[]; // raw config lines / command output supporting the finding
  rationale: string;
  remediation: string;
  status: FindingStatus;
  checked_at: string;
}

export interface ConfigSnapshot {
  snapshot_id: string;
  device_id: string;
  taken_at: string;
  line_count: number;
  content: string; // already sanitized by backend (secrets masked)
}

export interface DiffLine {
  kind: "add" | "remove" | "same";
  text: string;
}

export interface SnapshotDiff {
  device_id: string;
  from_snapshot_id: string;
  to_snapshot_id: string;
  lines: DiffLine[];
}

export interface AuditLogEntry {
  log_id: string;
  at: string;
  actor: string;
  action: string;
  target: string;
  result: "success" | "denied" | "error";
  detail: string;
}

export type ApprovalStatus = "pending" | "approved" | "rejected";
export type ExecutionStatus = "not_started" | "running" | "succeeded" | "failed";
export type ActionType = "create_vlan" | "configure_access_port";

export interface RemediationJob {
  job_id: string;
  action_type: ActionType;
  target_device: string; // device_id
  params: Record<string, string>;
  preview: string[]; // exact CLI lines that WOULD be sent (from backend template)
  validation_errors: string[];
  approval_status: ApprovalStatus;
  execution_status: ExecutionStatus;
  verification_result: { passed: boolean; detail: string } | null;
  created_at: string;
}

// ---- AI assistant (contract owned by C, consumed by B) ----
export interface AssistantExplanation {
  summary: string;
  why_it_matters: string;
  evidence_refs: string[];
  suggested_action: ActionType | null;
  suggested_params: Record<string, string>;
  confidence: "low" | "medium" | "high";
  caveats: string[];
}

export interface ExplainResponse {
  provider: string;
  explanation: AssistantExplanation | null;
  rejected_reason: string | null;
}
