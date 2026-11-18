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
