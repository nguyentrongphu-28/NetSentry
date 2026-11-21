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
