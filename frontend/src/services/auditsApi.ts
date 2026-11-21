import {
  AiExplanationOut,
  AiStatusOut,
  AuditRequestPayload,
  AuditRunDetailOut,
  AuditRunListOut,
  CompareOut,
  ConfigDiffOut,
  SnapshotDetailOut,
  SnapshotOut,
  BaselineOut,
  ApproveBaselineIn,
  DriftReportOut,
  DriftHistoryItemOut,
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

// ---------------------------------------------------------------------------
// Snapshot, Diff & AI APIs
// ---------------------------------------------------------------------------

export async function listDeviceSnapshots(deviceId: string): Promise<SnapshotOut[]> {
  return apiFetch<SnapshotOut[]>(`/api/v1/devices/${encodeURIComponent(deviceId)}/snapshots`);
}

export async function getSnapshot(snapshotId: number): Promise<SnapshotDetailOut> {
  return apiFetch<SnapshotDetailOut>(`/api/v1/snapshots/${snapshotId}`);
}

export async function deleteSnapshot(snapshotId: number): Promise<void> {
  await apiFetch<void>(`/api/v1/snapshots/${snapshotId}`, { method: "DELETE" });
}

export async function getDeviceConfigDiff(
  deviceId: string,
  fromRun?: number | null,
  toRun?: number | null,
): Promise<ConfigDiffOut> {
  const params = new URLSearchParams();
  if (fromRun !== undefined && fromRun !== null) params.set("from_run", String(fromRun));
  if (toRun !== undefined && toRun !== null) params.set("to_run", String(toRun));
  const queryStr = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<ConfigDiffOut>(`/api/v1/devices/${encodeURIComponent(deviceId)}/diff${queryStr}`);
}

export async function compareAuditRuns(runId: number, withRun?: number | null): Promise<CompareOut> {
  const params = new URLSearchParams();
  if (withRun !== undefined && withRun !== null) params.set("with", String(withRun));
  const queryStr = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<CompareOut>(`/api/v1/audits/${runId}/compare${queryStr}`);
}

export async function getAiStatus(): Promise<AiStatusOut> {
  return apiFetch<AiStatusOut>("/api/v1/ai/status");
}

export async function generateAuditExplanation(runId: number, force = false): Promise<AiExplanationOut> {
  const queryStr = force ? "?force=1" : "";
  return apiFetch<AiExplanationOut>(`/api/v1/audits/${runId}/explain${queryStr}`, {
    method: "POST",
  });
}

export async function getAuditExplanation(runId: number): Promise<AiExplanationOut> {
  return apiFetch<AiExplanationOut>(`/api/v1/audits/${runId}/explanation`);
}

// ---------------------------------------------------------------------------
// Baseline & Drift APIs
// ---------------------------------------------------------------------------

export async function getActiveBaseline(deviceId: string): Promise<BaselineOut> {
  return apiFetch<BaselineOut>(`/api/v1/devices/${encodeURIComponent(deviceId)}/baseline`);
}

export async function listBaselinesHistory(deviceId: string, limit = 50): Promise<BaselineOut[]> {
  return apiFetch<BaselineOut[]>(
    `/api/v1/devices/${encodeURIComponent(deviceId)}/baselines?limit=${limit}`
  );
}

export async function approveBaseline(
  deviceId: string,
  payload: ApproveBaselineIn
): Promise<BaselineOut> {
  return apiFetch<BaselineOut>(`/api/v1/devices/${encodeURIComponent(deviceId)}/baseline`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function retireActiveBaseline(deviceId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/devices/${encodeURIComponent(deviceId)}/baseline`, {
    method: "DELETE",
  });
}

export async function getDeviceDrift(
  deviceId: string,
  runId?: number | null,
  detail = false
): Promise<DriftReportOut> {
  const params = new URLSearchParams();
  if (runId !== undefined && runId !== null) params.set("run_id", String(runId));
  if (detail) params.set("detail", "1");
  const queryStr = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<DriftReportOut>(
    `/api/v1/devices/${encodeURIComponent(deviceId)}/drift${queryStr}`
  );
}

export const getDrift = getDeviceDrift;

export async function getDriftHistory(
  deviceId: string,
  limit = 30
): Promise<DriftHistoryItemOut[]> {
  return apiFetch<DriftHistoryItemOut[]>(
    `/api/v1/devices/${encodeURIComponent(deviceId)}/drift/history?limit=${limit}`
  );
}
