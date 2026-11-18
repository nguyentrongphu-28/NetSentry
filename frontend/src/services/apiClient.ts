import { ApiErrorResponse, isApiErrorResponse, ErrorDetail } from "../types/api";

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: ErrorDetail[] | null;

  constructor(status: number, code: string, message: string, details?: ErrorDetail[] | null) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  skipAuth?: boolean;
}

export const API_KEY_STORAGE_KEY = "netsentry.apiKey";

export function getStoredApiKey(): string | null {
  try {
    return sessionStorage.getItem(API_KEY_STORAGE_KEY);
  } catch {
    return null;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const isHealth = path === "/health" || path.startsWith("/health?");
  const skipAuth = options.skipAuth || isHealth;

  // Determine timeout: 120s for audit run, 15s otherwise
  const isAuditRun = path.includes("/audit") && options.method === "POST";
  const timeoutMs = options.timeoutMs ?? (isAuditRun ? 120000 : 15000);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  const headers = new Headers(options.headers || {});
  if (!skipAuth) {
    const key = getStoredApiKey();
    if (key) {
      headers.set("X-API-Key", key);
    }
  }

  // Ensure JSON content-type if body is provided and not already set
  if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(path, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (response.status === 401) {
      if (unauthorizedHandler) {
        unauthorizedHandler();
      }
      let errPayload: ApiErrorResponse | null = null;
      try {
        const json = await response.json();
        if (isApiErrorResponse(json)) {
          errPayload = json;
        }
      } catch {
        // Ignored
      }
      throw new ApiClientError(
        401,
        errPayload?.error.code || "UNAUTHORIZED",
        errPayload?.error.message || "Khóa API không hợp lệ hoặc đã hết hiệu lực."
      );
    }

    if (response.status === 204) {
      return undefined as unknown as T;
    }

    const contentType = response.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");

    if (!response.ok) {
      if (isJson) {
        try {
          const json = await response.json();
          if (isApiErrorResponse(json)) {
            throw new ApiClientError(
              response.status,
              json.error.code,
              json.error.message,
              json.error.details
            );
          }
        } catch (e) {
          if (e instanceof ApiClientError) throw e;
        }
      }
      throw new ApiClientError(
        response.status,
        "HTTP_ERROR",
        `Yêu cầu thất bại với mã trạng thái ${response.status}`
      );
    }

    if (!isJson) {
      return undefined as unknown as T;
    }

    return (await response.json()) as T;
  } catch (error: unknown) {
    if (error instanceof ApiClientError) {
      throw error;
    }

    if (controller.signal.aborted || (error instanceof Error && error.name === "AbortError")) {
      throw new ApiClientError(
        0,
        "CLIENT_TIMEOUT",
        `Yêu cầu vượt quá thời gian chờ (${Math.round(timeoutMs / 1000)}s)`
      );
    }

    throw new ApiClientError(
      0,
      "NETWORK_ERROR",
      "Không kết nối được tới máy chủ API. Kiểm tra mạng hoặc địa chỉ máy chủ."
    );
  } finally {
    clearTimeout(timeoutId);
  }
}
