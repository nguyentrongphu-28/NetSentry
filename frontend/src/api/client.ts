import type {
  ActionType, AuditLogEntry, ConfigSnapshot, Device, ExplainResponse, Finding,
  RemediationJob, ScanRun, SnapshotDiff,
} from "../types";
import { mockApi } from "./mock";

export interface Api {
  listDevices(): Promise<Device[]>;
  getDevice(id: string): Promise<Device>;
  testConnection(id: string): Promise<Device>;
  runScan(deviceId: string): Promise<ScanRun>;
  listScans(deviceId?: string): Promise<ScanRun[]>;
  listFindings(params?: { deviceId?: string; scanId?: string }): Promise<Finding[]>;
  listSnapshots(deviceId: string): Promise<ConfigSnapshot[]>;
  takeSnapshot(deviceId: string): Promise<ConfigSnapshot>;
  getDiff(deviceId: string, from: string, to: string): Promise<SnapshotDiff>;
  listAuditLogs(): Promise<AuditLogEntry[]>;
  previewRemediation(req: { action_type: ActionType; target_device: string; params: Record<string, string> }): Promise<RemediationJob>;
  approveRemediation(jobId: string): Promise<RemediationJob>;
  rejectRemediation(jobId: string): Promise<RemediationJob>;
  executeRemediation(jobId: string): Promise<RemediationJob>;
  verifyRemediation(jobId: string): Promise<RemediationJob>;
  explainFinding(req: { finding: Finding; question?: string }): Promise<ExplainResponse>;
}

import { ApiError } from "./errors";
export { ApiError };

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { const body = await res.json(); msg = body.detail ?? JSON.stringify(body); } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}
const post = <T,>(p: string, body?: unknown) =>
  http<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

// Real API: paths follow docs/api-contract.md (plan section 5.1).
const realApi: Api = {
  listDevices: () => http("/devices"),
  getDevice: (id) => http(`/devices/${id}`),
  testConnection: (id) => post(`/devices/${id}/test-connection`),
  runScan: (id) => post(`/devices/${id}/scans`),
  listScans: (id) => http(id ? `/devices/${id}/scans` : "/scans"),
  listFindings: (p) => {
    if (p?.scanId) return http(`/scans/${p.scanId}/findings`);
    return http(p?.deviceId ? `/devices/${p.deviceId}/findings` : "/findings");
  },
  listSnapshots: (id) => http(`/devices/${id}/snapshots`),
  takeSnapshot: (id) => post(`/devices/${id}/snapshots`),
  getDiff: (id, from, to) => http(`/devices/${id}/diff?from=${from}&to=${to}`),
  listAuditLogs: () => http("/audit-logs"),
  previewRemediation: (r) => post("/remediations/preview", r),
  approveRemediation: (id) => post(`/remediations/${id}/approve`),
  rejectRemediation: (id) => post(`/remediations/${id}/reject`),
  executeRemediation: (id) => post(`/remediations/${id}/execute`),
  verifyRemediation: (id) => http(`/remediations/${id}/verify`),
  explainFinding: (r) => post("/assistant/explain", r),
};

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";
export const api: Api = USE_MOCK ? mockApi : realApi;
