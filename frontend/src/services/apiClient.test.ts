import { describe, it, expect, vi, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/msw/server";
import {
  apiFetch,
  ApiClientError,
  setUnauthorizedHandler,
  API_KEY_STORAGE_KEY,
} from "./apiClient";

describe("apiClient", () => {
  beforeEach(() => {
    sessionStorage.clear();
    setUnauthorizedHandler(null);
  });

  it("sends X-API-Key header when key exists in sessionStorage", async () => {
    sessionStorage.setItem(API_KEY_STORAGE_KEY, "test-valid-key");
    let receivedHeader: string | null = null;

    server.use(
      http.get("/api/v1/test", ({ request }) => {
        receivedHeader = request.headers.get("X-API-Key");
        return HttpResponse.json({ success: true });
      })
    );

    const result = await apiFetch<{ success: boolean }>("/api/v1/test");
    expect(result).toEqual({ success: true });
    expect(receivedHeader).toBe("test-valid-key");
  });

  it("does not send X-API-Key header for /health", async () => {
    sessionStorage.setItem(API_KEY_STORAGE_KEY, "test-secret-key");
    let receivedHeader: string | null = null;

    server.use(
      http.get("/health", ({ request }) => {
        receivedHeader = request.headers.get("X-API-Key");
        return HttpResponse.json({ status: "ok" });
      })
    );

    await apiFetch("/health");
    expect(receivedHeader).toBeNull();
  });

  it("parses API error format { error: { code, message, details } }", async () => {
    server.use(
      http.get("/api/v1/fail", () => {
        return HttpResponse.json(
          {
            error: {
              code: "VALIDATION_FAILED",
              message: "Device ID is invalid.",
              details: [{ field: "device_id", message: "Pattern mismatch" }],
            },
          },
          { status: 422 }
        );
      })
    );

    await expect(apiFetch("/api/v1/fail")).rejects.toThrow(ApiClientError);
    try {
      await apiFetch("/api/v1/fail");
    } catch (e) {
      const err = e as ApiClientError;
      expect(err.status).toBe(422);
      expect(err.code).toBe("VALIDATION_FAILED");
      expect(err.message).toBe("Device ID is invalid.");
      expect(err.details).toEqual([{ field: "device_id", message: "Pattern mismatch" }]);
    }
  });

  it("triggers unauthorized handler on HTTP 401", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    server.use(
      http.get("/api/v1/protected", () => {
        return HttpResponse.json(
          { error: { code: "UNAUTHORIZED", message: "Bad key" } },
          { status: 401 }
        );
      })
    );

    await expect(apiFetch("/api/v1/protected")).rejects.toThrow(ApiClientError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("handles network error gracefully as a generic error", async () => {
    server.use(
      http.get("/api/v1/network-fail", () => {
        return HttpResponse.error();
      })
    );

    await expect(apiFetch("/api/v1/network-fail")).rejects.toThrow(ApiClientError);
    try {
      await apiFetch("/api/v1/network-fail");
    } catch (e) {
      const err = e as ApiClientError;
      expect(err.code).toBe("NETWORK_ERROR");
      expect(err.status).toBe(0);
    }
  });

  it("uses 120s timeout for audit run and aborts on timeout", async () => {
    vi.useFakeTimers();

    server.use(
      http.post("/api/v1/devices/R1/audit", async () => {
        // Delay response beyond timeout
        await new Promise((r) => setTimeout(r, 130000));
        return HttpResponse.json({ status: "COMPLETED" });
      })
    );

    const fetchPromise = apiFetch("/api/v1/devices/R1/audit", { method: "POST" });
    const assertionPromise = expect(fetchPromise).rejects.toMatchObject({
      code: "CLIENT_TIMEOUT",
    });

    // Fast-forward past 120s
    await vi.advanceTimersByTimeAsync(121000);

    await assertionPromise;
    vi.useRealTimers();
  });
});
