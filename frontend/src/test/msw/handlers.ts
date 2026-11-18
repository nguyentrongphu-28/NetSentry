import { http, HttpResponse } from "msw";
import {
  mockAuditRunDetail,
  mockAuditRunHistory,
  mockAuditSummaryFailed,
  mockCreatedDevice,
  mockDevice1,
  mockDeviceList,
  mockHealth,
} from "../fixtures";

export const handlers = [
  // Health
  http.get("/health", () => {
    return HttpResponse.json(mockHealth);
  }),

  // List devices
  http.get("/api/v1/devices", ({ request }) => {
    const apiKey = request.headers.get("X-API-Key");
    if (!apiKey || apiKey === "invalid-key") {
      return HttpResponse.json(
        {
          error: {
            code: "UNAUTHORIZED",
            message: "Invalid or missing API key.",
          },
        },
        { status: 401 }
      );
    }
    return HttpResponse.json(mockDeviceList);
  }),

  // Get device
  http.get("/api/v1/devices/:deviceId", ({ params }) => {
    const { deviceId } = params;
    if (deviceId === "non-existent") {
      return HttpResponse.json(
        {
          error: {
            code: "DEVICE_NOT_FOUND",
            message: `Device '${deviceId}' not found.`,
          },
        },
        { status: 404 }
      );
    }
    return HttpResponse.json({
      ...mockDevice1,
      device_id: deviceId,
    });
  }),

  // Create device
  http.post("/api/v1/devices", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    if (body.device_id === "existing-device") {
      return HttpResponse.json(
        {
          error: {
            code: "DEVICE_EXISTS",
            message: "Device already exists.",
          },
        },
        { status: 409 }
      );
    }
    return HttpResponse.json(mockCreatedDevice, { status: 201 });
  }),

  // Delete device
  http.delete("/api/v1/devices/:deviceId", () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Run audit
  http.post("/api/v1/devices/:deviceId/audit", async ({ params, request }) => {
    const { deviceId } = params;
    if (deviceId === "running-device") {
      return HttpResponse.json(
        {
          error: {
            code: "AUDIT_ALREADY_RUNNING",
            message: "Audit already running for this device.",
          },
        },
        { status: 409 }
      );
    }

    if (deviceId === "non-existent") {
      return HttpResponse.json(
        {
          error: {
            code: "DEVICE_NOT_FOUND",
            message: "Device not found.",
          },
        },
        { status: 404 }
      );
    }

    const body = (await request.json().catch(() => null)) as {
      credentials?: { username?: string; password?: string };
    } | null;

    if (!body?.credentials?.username || !body?.credentials?.password) {
      return HttpResponse.json(
        {
          error: {
            code: "CREDENTIALS_REQUIRED",
            message: "Credentials are required for audit.",
          },
        },
        { status: 422 }
      );
    }

    if (deviceId === "failed-device") {
      return HttpResponse.json(
        {
          summary: mockAuditSummaryFailed,
          findings: [],
        },
        { status: 201 }
      );
    }

    return HttpResponse.json(mockAuditRunDetail, { status: 201 });
  }),

  // List device audits
  http.get("/api/v1/devices/:deviceId/audits", () => {
    return HttpResponse.json(mockAuditRunHistory);
  }),

  // Get audit run
  http.get("/api/v1/audits/:runId", ({ params }) => {
    const { runId } = params;
    if (runId === "999") {
      return HttpResponse.json(
        {
          error: {
            code: "AUDIT_NOT_FOUND",
            message: "Audit run not found.",
          },
        },
        { status: 404 }
      );
    }
    return HttpResponse.json(mockAuditRunDetail);
  }),
];
