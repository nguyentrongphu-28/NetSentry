import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RunAuditDialog } from "./RunAuditDialog";
import { mockDevice1, mockAuditRunDetail } from "../../test/fixtures";
import { server } from "../../test/msw/server";
import { http, HttpResponse } from "msw";
import { STRINGS } from "../../i18n/strings";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderDialog(props = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const defaultProps = {
    device: mockDevice1,
    isOpen: true,
    onClose: vi.fn(),
    onAuditCompletedInBackground: vi.fn(),
    ...props,
  };

  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <RunAuditDialog {...defaultProps} />
        </MemoryRouter>
      </QueryClientProvider>
    ),
    props: defaultProps,
  };
}

describe("RunAuditDialog (Section 7.5)", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    server.resetHandlers();
    sessionStorage.clear();
    localStorage.clear();
    sessionStorage.setItem("netsentry.apiKey", "valid-key");
  });

  it("requires username and password fields on submit", async () => {
    const user = userEvent.setup();
    renderDialog();

    expect(screen.getByText("Router-Core-01")).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: "Bắt đầu audit" });
    await user.click(submitBtn);

    expect(await screen.findByText("Vui lòng nhập tên đăng nhập SSH.")).toBeInTheDocument();
    expect(screen.getByText("Vui lòng nhập mật khẩu SSH.")).toBeInTheDocument();
  });

  it("submits manual credentials and navigates to audit detail on 201 COMPLETED", async () => {
    const user = userEvent.setup();
    renderDialog();

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: "secret123" } });

    const submitBtn = screen.getByRole("button", { name: "Bắt đầu audit" });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/audits/101");
    });
  });

  it("navigates to audit detail on 201 FAILED run as well", async () => {
    const user = userEvent.setup();
    const failedDevice = { ...mockDevice1, device_id: "failed-device" };
    renderDialog({ device: failedDevice });

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: "wrong_password" } });

    const submitBtn = screen.getByRole("button", { name: "Bắt đầu audit" });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/audits/102");
    });
  });

  it("prevents double submission: counts MSW handler calls and asserts exactly 1 on double-click", async () => {
    let callCount = 0;
    let resolveRequest: () => void;
    const requestPromise = new Promise<void>((resolve) => {
      resolveRequest = resolve;
    });

    server.use(
      http.post("/api/v1/devices/:deviceId/audit", async () => {
        callCount++;
        await requestPromise;
        return HttpResponse.json(mockAuditRunDetail, { status: 201 });
      })
    );

    const user = userEvent.setup();
    renderDialog();

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: "secret123" } });

    const submitBtn = screen.getByRole("button", { name: "Bắt đầu audit" });
    // Click twice rapidly
    await user.click(submitBtn);
    await user.click(submitBtn);

    expect(submitBtn).toBeDisabled();
    expect(callCount).toBe(1);

    resolveRequest!();
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/audits/101");
    });
    mockNavigate.mockClear();
  });

  it("prevents double submission: pressing Enter twice only triggers exactly 1 API call", async () => {
    let callCount = 0;
    let resolveRequest: () => void;
    const requestPromise = new Promise<void>((resolve) => {
      resolveRequest = resolve;
    });

    server.use(
      http.post("/api/v1/devices/:deviceId/audit", async () => {
        callCount++;
        await requestPromise;
        return HttpResponse.json(mockAuditRunDetail, { status: 201 });
      })
    );

    const user = userEvent.setup();
    renderDialog();

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    await user.type(usernameInput, "cisco_admin");
    await user.type(passwordInput, "secret123");

    const form = passwordInput.closest("form")!;
    // Submit form twice with Enter / submit event
    fireEvent.submit(form);
    fireEvent.submit(form);

    await waitFor(() => {
      expect(callCount).toBe(1);
    });

    resolveRequest!();
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/audits/101");
    });
    mockNavigate.mockClear();
  });

  it("does not navigate when dialog is closed before audit completes, triggers background callback", async () => {
    let resolveRequest: () => void;
    const requestPromise = new Promise<void>((resolve) => {
      resolveRequest = resolve;
    });

    server.use(
      http.post("/api/v1/devices/:deviceId/audit", async () => {
        await requestPromise;
        return HttpResponse.json(mockAuditRunDetail, { status: 201 });
      })
    );

    const onAuditCompletedInBackground = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderDialog({ onClose, onAuditCompletedInBackground });

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: "secret123" } });

    await user.click(screen.getByRole("button", { name: "Bắt đầu audit" }));

    // User closes dialog while request is in flight
    const cancelBtn = screen.getByRole("button", { name: "Đóng" });
    await user.click(cancelBtn);
    expect(onClose).toHaveBeenCalled();

    // Now resolve the server response
    resolveRequest!();

    await waitFor(() => {
      expect(onAuditCompletedInBackground).toHaveBeenCalledWith(101, "Router-Core-01");
    });
    // Should NOT have navigated
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("displays server error 409 AUDIT_ALREADY_RUNNING", async () => {
    const user = userEvent.setup();
    const runningDevice = { ...mockDevice1, device_id: "running-device" };
    renderDialog({ device: runningDevice });

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: "secret123" } });

    await user.click(screen.getByRole("button", { name: "Bắt đầu audit" }));

    expect(
      await screen.findByText("Thiết bị đang được audit bởi tiến trình khác.")
    ).toBeInTheDocument();
  });

  it("displays server error 404 DEVICE_NOT_FOUND", async () => {
    const user = userEvent.setup();
    const missingDevice = { ...mockDevice1, device_id: "non-existent" };
    renderDialog({ device: missingDevice });

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: "secret123" } });

    await user.click(screen.getByRole("button", { name: "Bắt đầu audit" }));

    expect(
      await screen.findByText("Thiết bị không còn tồn tại trên máy chủ.")
    ).toBeInTheDocument();
  });

  it("displays 422 VALIDATION_ERROR with field errors from details attached to inputs", async () => {
    server.use(
      http.post("/api/v1/devices/:deviceId/audit", () => {
        return HttpResponse.json(
          {
            error: {
              code: "VALIDATION_ERROR",
              message: "Dữ liệu xác thực không hợp lệ.",
              details: [
                { field: "username", message: "Tên đăng nhập chứa ký tự cấm." },
                { field: "password", message: "Mật khẩu quá ngắn." },
              ],
            },
          },
          { status: 422 }
        );
      })
    );

    const user = userEvent.setup();
    renderDialog();

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "bad_user!" } });
    fireEvent.change(passwordInput, { target: { value: "123" } });

    await user.click(screen.getByRole("button", { name: "Bắt đầu audit" }));

    expect(await screen.findByText("Tên đăng nhập chứa ký tự cấm.")).toBeInTheDocument();
    expect(screen.getByText("Mật khẩu quá ngắn.")).toBeInTheDocument();
  });

  it("displays notice when client timeout occurs (CLIENT_TIMEOUT)", async () => {
    server.use(
      http.post("/api/v1/devices/:deviceId/audit", () => {
        return HttpResponse.json(
          {
            error: {
              code: "CLIENT_TIMEOUT",
              message: "Yêu cầu kiểm toán đã quá thời gian chờ (120s).",
            },
          },
          { status: 504 }
        );
      })
    );

    const user = userEvent.setup();
    renderDialog();

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: "secret123" } });

    await user.click(screen.getByRole("button", { name: "Bắt đầu audit" }));

    expect(
      await screen.findByText(STRINGS.runAuditDialog.timeoutNotice)
    ).toBeInTheDocument();
  });

  it("security test: secret FAKE-UI-PW never leaks to console, storage, or DOM after close", async () => {
    const FAKE_PW = "FAKE-UI-PW-SECRET";
    const consoleSpy = vi.spyOn(console, "log");
    const consoleWarnSpy = vi.spyOn(console, "warn");
    const consoleErrorSpy = vi.spyOn(console, "error");

    const onClose = vi.fn();
    const { unmount } = renderDialog({ onClose });

    const usernameInput = screen.getByLabelText(/tên đăng nhập ssh/i);
    const passwordInput = screen.getByLabelText(/mật khẩu ssh \*/i);

    fireEvent.change(usernameInput, { target: { value: "cisco_admin" } });
    fireEvent.change(passwordInput, { target: { value: FAKE_PW } });

    // Close the dialog
    const closeBtn = screen.getByRole("button", { name: "Đóng" });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();

    unmount();

    // Verify secret is not in sessionStorage or localStorage
    expect(JSON.stringify(sessionStorage)).not.toContain(FAKE_PW);
    expect(JSON.stringify(localStorage)).not.toContain(FAKE_PW);

    // Verify secret is not logged to console
    const checkCalls = (calls: unknown[][]) =>
      calls.every((args) => args.every((arg) => typeof arg !== "string" || !arg.includes(FAKE_PW)));

    expect(checkCalls(consoleSpy.mock.calls)).toBe(true);
    expect(checkCalls(consoleWarnSpy.mock.calls)).toBe(true);
    expect(checkCalls(consoleErrorSpy.mock.calls)).toBe(true);

    // Verify secret is not anywhere in the DOM
    expect(document.body.innerHTML).not.toContain(FAKE_PW);

    consoleSpy.mockRestore();
    consoleWarnSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });
});
