/**
 * NetSentry API Types
 * Strictly mirrored from backend schemas in backend/app/api/schemas/
 */

export interface ErrorDetail {
  field: string;
  message: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
  details?: ErrorDetail[] | null;
}

export interface ApiErrorResponse {
  error: ErrorPayload;
}

export function isApiErrorResponse(data: unknown): data is ApiErrorResponse {
  if (typeof data !== "object" || data === null) {
    return false;
  }
  const errorObj = (data as Record<string, unknown>).error;
  if (typeof errorObj !== "object" || errorObj === null) {
    return false;
  }
  const payload = errorObj as Record<string, unknown>;
  return typeof payload.code === "string" && typeof payload.message === "string";
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface DeviceCreatePayload {
  device_id: string;
  host: string;
  name?: string | null;
  port?: number;
  platform?: "cisco_ios";
}

export interface DeviceOut {
  device_id: string;
  name: string;
  host: string;
  port: number;
  platform: string;
  created_at: string;
  updated_at: string;
}

export interface DeviceWithLatestAuditOut extends DeviceOut {
  latest_audit?: AuditRunSummaryOut | null;
}

export interface DeviceListOut {
  items: DeviceWithLatestAuditOut[];
}

export interface CredentialsIn {
  username: string;
  password: string;
  enable_secret?: string | null;
}

export interface AuditRequestPayload {
  credentials?: CredentialsIn | null;
}

export type AuditRunStatus = "COMPLETED" | "FAILED";
export type FindingSeverity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type FindingStatus = "PASS" | "FAIL" | "UNKNOWN";

export interface AuditRunSummaryOut {
  id: number;
  device_id: string;
  platform: string;
  status: AuditRunStatus;
  started_at: string;
  finished_at: string;
  hostname?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  pass_count: number;
  fail_count: number;
  unknown_count: number;
}

export interface FindingOut {
  rule_id: string;
  title: string;
  severity: FindingSeverity;
  status: FindingStatus;
  evidence: string[];
  rationale: string;
  remediation: string;
  verification: string;
  checked_at?: string | null;
}

export interface AuditRunDetailOut {
  summary: AuditRunSummaryOut;
  findings: FindingOut[];
}

export interface AuditRunListOut {
  items: AuditRunSummaryOut[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Auth, RBAC & Users Types
// ---------------------------------------------------------------------------

export type UserRole = "admin" | "operator" | "viewer";

export interface UserSummary {
  id: number;
  username: string;
  role: UserRole;
  must_change_password: boolean;
}

export interface Capabilities {
  body_credentials: boolean;
}

export interface AuthMeResponse {
  user: UserSummary;
  capabilities: Capabilities;
}

export interface UserRecord {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface SecurityEventRecord {
  id: number;
  occurred_at: string;
  event_type: string;
  actor_username?: string | null;
  client_ip?: string | null;
  target?: string | null;
  detail?: string | null;
}

// ---------------------------------------------------------------------------
// Snapshot & Diff & AI Types
// ---------------------------------------------------------------------------

export interface SnapshotOut {
  id: number;
  device_id: string;
  run_id: number;
  created_at: string;
  content_sha256: string;
  size_bytes: number;
  line_count: number;
  redaction_version: number;
}

export interface SnapshotDetailOut extends SnapshotOut {
  content: string;
}

export interface DiffLineOut {
  op: " " | "+" | "-";
  text: string;
}

export interface DiffHunkOut {
  old_start: number;
  new_start: number;
  lines: DiffLineOut[];
}

export interface ConfigDiffOut {
  from_run_id: number;
  to_run_id: number;
  identical: boolean;
  added: number;
  removed: number;
  hunks: DiffHunkOut[];
  truncated: boolean;
}

export type ChangeKind = "REGRESSION" | "FIXED" | "PERSISTING" | "UNCHANGED_OK" | "OTHER";

export interface FindingChangeOut {
  rule_id: string;
  title: string;
  before_status?: string | null;
  after_status?: string | null;
  before_severity?: string | null;
  after_severity?: string | null;
  kind: ChangeKind;
}

export interface CompareOut {
  from_run_id?: number | null;
  to_run_id: number;
  device_id: string;
  has_previous: boolean;
  changes: FindingChangeOut[];
  counts: Record<string, number>;
}

export interface AiStatusOut {
  enabled: boolean;
  reachable: boolean;
  model: string;
}

export interface PriorityItemOut {
  rule_id: string;
  reason: string;
}

export interface RiskNoteOut {
  rule_id: string;
  warning: string;
}

export interface AiExplanationOut {
  run_id: number;
  created_at: string;
  model: string;
  prompt_version: number;
  input_sha256: string;
  summary: string;
  priorities: PriorityItemOut[];
  risks: RiskNoteOut[];
  generated_by_ai: boolean;
}

// ---------------------------------------------------------------------------
// Baseline & Drift Types
// ---------------------------------------------------------------------------

export type BaselineStatus = "ACTIVE" | "RETIRED";

export interface BaselineOut {
  id: number;
  device_id: string;
  snapshot_id: number;
  content_sha256: string;
  status: BaselineStatus;
  approved_by: string;
  approved_at: string;
  note: string | null;
  fail_count_at_approval: number;
  retired_at?: string | null;
  retired_by?: string | null;
}

export interface ApproveBaselineIn {
  snapshot_id: number;
  note?: string | null;
  confirm_with_failures?: boolean;
}

export type BlockChangeKind = "ADDED" | "REMOVED" | "CHANGED";

export interface BlockChangeOut {
  key: string;
  kind: BlockChangeKind;
  security_relevant: boolean;
  added_lines: string[];
  removed_lines: string[];
  added_count: number;
  removed_count: number;
}

export interface DriftSummaryOut {
  status: "IN_SYNC" | "DRIFTED";
  added_blocks: number;
  removed_blocks: number;
  changed_blocks: number;
  security_relevant_count: number;
}

export interface DriftReportOut {
  device_id: string;
  baseline_id: number;
  run_id: number;
  lines_included: boolean;
  summary: DriftSummaryOut;
  blocks: BlockChangeOut[];
  truncated: boolean;
}

export interface DriftHistoryItemOut {
  run_id: number;
  device_id: string;
  baseline_id: number;
  checked_at: string;
  status: "IN_SYNC" | "DRIFTED";
  added_blocks: number;
  removed_blocks: number;
  changed_blocks: number;
  security_relevant_count: number;
}

export type RemediationPlanStatus =
  | "PROPOSED"
  | "APPROVED"
  | "REJECTED"
  | "CANCELLED"
  | "EXPIRED"
  | "APPLYING"
  | "APPLIED"
  | "VERIFIED"
  | "VERIFY_FAILED"
  | "FAILED"
  | "ROLLED_BACK";

export type RemediationRiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface ProposePlanIn {
  persist_after_verify: boolean;
}

export interface ApprovePlanIn {
  password: string;
}

export interface RejectPlanIn {
  reason: string;
}

export interface PlanEventOut {
  id: number;
  plan_id: number;
  occurred_at: string;
  actor: string | null;
  event_type: string;
  detail: string | null;
}

export interface ExpectedVerificationOut {
  rule_id: string;
  expected_status: string;
}

export interface RemediationPlanOut {
  id: number;
  device_id: string;
  run_id: number;
  rule_id: string;
  status: RemediationPlanStatus;
  risk_level: RemediationRiskLevel;
  persist_after_verify: boolean;
  proposed_by: string;
  proposed_at: string;
  decided_by?: string | null;
  decided_at?: string | null;
  expires_at: string;
  plan_hash: string;
}

export interface RemediationPlanDetailOut extends RemediationPlanOut {
  commands: string[];
  impact: string;
  risks: string;
  expected_verification: ExpectedVerificationOut;
  reversible: boolean;
  rollback_note: string;
  decide_reason?: string | null;
  approved_hash_matches: boolean;
  timeline: PlanEventOut[];
}

export interface RemediationTemplateOut {
  rule_id: string;
  version: string;
  title: string;
  commands: string[];
  risk_level: RemediationRiskLevel;
  impact: string;
  risks: string;
  reversible: boolean;
  rollback_note: string;
  platforms: string[];
}

export interface ManualGuidanceOut {
  rule_id: string;
  title: string;
  remediation_guide: string;
  verification_guide: string;
  why_not_automated: string;
}

export interface TemplatesResponseOut {
  templates: RemediationTemplateOut[];
  manual_guidance: ManualGuidanceOut[];
}

