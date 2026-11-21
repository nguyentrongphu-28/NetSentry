import {
  AuditRequestPayload,
  AuditRunDetailOut,
  AuditRunListOut,
} from "../types/api";
import { apiFetch } from "./apiClient";

export async function runDeviceAudit(
  deviceId: string,
  payload?: AuditRequestPayload | null
): Promise<AuditRunDetailOut> {
  const options: RequestInit = {
    method: "POST",
  };

  // Only attach body if payload with credentials is provided
  if (payload && payload.credentials) {
    options.body = JSON.stringify(payload);
  }

  return apiFetch<AuditRunDetailOut>(
    `/api/v1/devices/${encodeURIComponent(deviceId)}/audit`,
    options
  );
}

export async function listDeviceAudits(
  deviceId: string,
  limit = 20,
  offset = 0
): Promise<AuditRunListOut> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });
  return apiFetch<AuditRunListOut>(
    `/api/v1/devices/${encodeURIComponent(deviceId)}/audits?${params.toString()}`
  );
}

export async function getAuditRun(runId: number): Promise<AuditRunDetailOut> {
  return apiFetch<AuditRunDetailOut>(`/api/v1/audits/${runId}`);
}

// ----- Additional API functions for Snapshot & AI -----
// Config diff API
export async function fetchConfigDiff(deviceId: string, toRunId: number): Promise<unknown> {
  // GET /devices/{id}/diff?from_run=&to_run=toRunId (from_run omitted -> previous run)
  return apiFetch<unknown>(`/api/v1/devices/${encodeURIComponent(deviceId)}/diff?to_run=${toRunId}`);
}

// AI explain API
export async function postExplainAuditRun(runId: number, force = false): Promise<unknown> {
  const url = `/api/v1/audits/${runId}/explain${force ? "?force=1" : ""}`;
  return apiFetch<unknown>(url, { method: "POST" });
}

export async function getAuditExplanation(runId: number): Promise<unknown> {
  return apiFetch<unknown>(`/api/v1/audits/${runId}/explanation`);
}

// Snapshot APIs
export async function listDeviceSnapshots(deviceId: string): Promise<unknown> {
  return apiFetch<unknown>(`/api/v1/devices/${encodeURIComponent(deviceId)}/snapshots`);
}

export async function getSnapshotContent(snapshotId: number): Promise<unknown> {
  return apiFetch<unknown>(`/api/v1/snapshots/${snapshotId}`);
}

export async function deleteSnapshot(snapshotId: number): Promise<void> {
  await apiFetch<void>(`/api/v1/snapshots/${snapshotId}`, { method: "DELETE" });
}

export async function fetchConfigDiff(deviceId: string, toRunId: number): Promise<any> {
  // GET /devices/{id}/diff?from_run=&to_run=toRunId (from_run omitted -> previous run)
  return apiFetch<any>(`/api/v1/devices/${encodeURIComponent(deviceId)}/diff?to_run=${toRunId}`);
}

// AI explain API
export async function postExplainAuditRun(runId: number, force = false): Promise<any> {
  const url = `/api/v1/audits/${runId}/explain${force ? "?force=1" : ""}`;
  return apiFetch<any>(url, { method: "POST" });
}

export async function getAuditExplanation(runId: number): Promise<any> {
  return apiFetch<any>(`/api/v1/audits/${runId}/explanation`);
}

// Snapshot APIs
export async function listDeviceSnapshots(deviceId: string): Promise<any> {
  return apiFetch<any>(`/api/v1/devices/${encodeURIComponent(deviceId)}/snapshots`);
}

export async function getSnapshotContent(snapshotId: number): Promise<any> {
  return apiFetch<any>(`/api/v1/snapshots/${snapshotId}`);
}

export async function deleteSnapshot(snapshotId: number): Promise<void> {
  await apiFetch<void>(`/api/v1/snapshots/${snapshotId}`, { method: "DELETE" });
}
