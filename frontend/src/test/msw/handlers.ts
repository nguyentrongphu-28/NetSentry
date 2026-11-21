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

  // Auth Me
  http.get("/api/v1/auth/me", () => {
    return HttpResponse.json({
      user: {
        id: 1,
        username: "admin",
        role: "admin",
        must_change_password: false,
      },
      capabilities: {
        body_credentials: true,
      },
    });
  }),

  // Auth Login
  http.post("/api/v1/auth/login", async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as {
      username?: string;
      password?: string;
    };
    if (body.username === "locked_user") {
      return HttpResponse.json(
        {
          error: {
            code: "RATE_LIMITED",
            message: "Tài khoản tạm thời bị khóa. Vui lòng thử lại sau.",
          },
        },
        { status: 429 }
      );
    }
    if (body.username !== "admin" || body.password !== "Admin@Pass1234") {
      return HttpResponse.json(
        {
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Sai tên đăng nhập hoặc mật khẩu.",
          },
        },
        { status: 401 }
      );
    }
    return HttpResponse.json({
      user: {
        id: 1,
        username: "admin",
        role: "admin",
        must_change_password: false,
      },
    });
  }),

  // Auth Logout
  http.post("/api/v1/auth/logout", () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Auth Change Password
  http.post("/api/v1/auth/change-password", () => {
    return HttpResponse.json({ status: "ok" });
  }),

  // List Users
  http.get("/api/v1/users", () => {
    return HttpResponse.json([
      {
        id: 1,
        username: "admin",
        role: "admin",
        is_active: true,
        must_change_password: false,
        created_at: "2026-01-01T00:00:00Z",
        last_login_at: "2026-01-01T01:00:00Z",
      },
      {
        id: 2,
        username: "operator1",
        role: "operator",
        is_active: true,
        must_change_password: false,
        created_at: "2026-01-01T00:00:00Z",
        last_login_at: null,
      },
    ]);
  }),

  // Create User
  http.post("/api/v1/users", async ({ request }) => {
    const body = (await request.json()) as { username: string; role: string };
    if (body.username === "existing_user") {
      return HttpResponse.json(
        {
          error: {
            code: "USER_EXISTS",
            message: "User exists.",
          },
        },
        { status: 409 }
      );
    }
    return HttpResponse.json(
      {
        id: 3,
        username: body.username,
        role: body.role,
        is_active: true,
        must_change_password: true,
        created_at: "2026-01-02T00:00:00Z",
      },
      { status: 201 }
    );
  }),

  // Update User
  http.patch("/api/v1/users/:userId", async ({ params, request }) => {
    const body = (await request.json()) as { role?: string; is_active?: boolean };
    if (params.userId === "1" && (body.role === "viewer" || body.is_active === false)) {
      return HttpResponse.json(
        {
          error: {
            code: "LAST_ADMIN",
            message: "Không thể hạ quyền hoặc vô hiệu hóa admin cuối cùng.",
          },
        },
        { status: 409 }
      );
    }
    return HttpResponse.json({
      id: Number(params.userId),
      username: "updated_user",
      role: body.role || "operator",
      is_active: body.is_active ?? true,
      must_change_password: false,
      created_at: "2026-01-01T00:00:00Z",
    });
  }),

  // Reset Password
  http.post("/api/v1/users/:userId/reset-password", () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Security Events
  http.get("/api/v1/security-events", () => {
    return HttpResponse.json([
      {
        id: 1,
        occurred_at: "2026-01-01T00:00:00Z",
        event_type: "LOGIN_SUCCESS",
        actor_username: "admin",
        client_ip: "127.0.0.1",
        target: null,
        detail: null,
      },
    ]);
  }),

  // List devices
  http.get("/api/v1/devices", () => {
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
