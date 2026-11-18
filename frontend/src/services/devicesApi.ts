import {
  DeviceCreatePayload,
  DeviceListOut,
  DeviceOut,
  DeviceWithLatestAuditOut,
  HealthResponse,
} from "../types/api";
import { apiFetch } from "./apiClient";

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health", { skipAuth: true });
}

export async function listDevices(): Promise<DeviceListOut> {
  return apiFetch<DeviceListOut>("/api/v1/devices");
}

export async function getDevice(deviceId: string): Promise<DeviceWithLatestAuditOut> {
  return apiFetch<DeviceWithLatestAuditOut>(`/api/v1/devices/${encodeURIComponent(deviceId)}`);
}

export async function createDevice(payload: DeviceCreatePayload): Promise<DeviceOut> {
  return apiFetch<DeviceOut>("/api/v1/devices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteDevice(deviceId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/devices/${encodeURIComponent(deviceId)}`, {
    method: "DELETE",
  });
}
