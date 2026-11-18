import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiKeyProvider } from "../hooks/useApiKey";
import { AppRoutes } from "../App";
import { API_KEY_STORAGE_KEY } from "../services/apiClient";

function renderWithProviders(initialRoute = "/"): ReturnType<typeof render> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiKeyProvider>
        <MemoryRouter initialEntries={[initialRoute]}>
          <AppRoutes />
        </MemoryRouter>
      </ApiKeyProvider>
    </QueryClientProvider>
  );
}

describe("Auth and Routing (Section 7.2)", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("redirects unauthenticated user from / to /connect", async () => {
    renderWithProviders("/");
    expect(await screen.findByRole("button", { name: /kết nối/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/khóa api/i)).toBeInTheDocument();
  });

  it("shows error when entering invalid API key", async () => {
    const user = userEvent.setup();
    renderWithProviders("/connect");

    const input = await screen.findByLabelText(/khóa api/i);
    await user.type(input, "invalid-key");
    await user.click(screen.getByRole("button", { name: /kết nối/i }));

    expect(await screen.findByText(/khóa api không đúng/i)).toBeInTheDocument();
    expect(sessionStorage.getItem(API_KEY_STORAGE_KEY)).toBeNull();
  });

  it("successfully connects with valid key and saves to sessionStorage only", async () => {
    const user = userEvent.setup();
    renderWithProviders("/connect");

    const input = await screen.findByLabelText(/khóa api/i);
    await user.type(input, "my-valid-api-key");
    await user.click(screen.getByRole("button", { name: /kết nối/i }));

    // Navigates to dashboard
    expect(await screen.findByText("Danh sách thiết bị")).toBeInTheDocument();

    // Verifies key is saved to sessionStorage and NEVER to localStorage
    expect(sessionStorage.getItem(API_KEY_STORAGE_KEY)).toBe("my-valid-api-key");
    expect(localStorage.getItem(API_KEY_STORAGE_KEY)).toBeNull();
    expect(localStorage.length).toBe(0);
  });

  it("logs out, clears key from sessionStorage and redirects to /connect", async () => {
    sessionStorage.setItem(API_KEY_STORAGE_KEY, "my-valid-api-key");
    const user = userEvent.setup();
    renderWithProviders("/");

    expect(await screen.findByText("Danh sách thiết bị")).toBeInTheDocument();

    const logoutBtn = screen.getByRole("button", { name: /đăng xuất/i });
    await user.click(logoutBtn);

    expect(await screen.findByRole("button", { name: /kết nối/i })).toBeInTheDocument();
    expect(sessionStorage.getItem(API_KEY_STORAGE_KEY)).toBeNull();
  });

  it("redirects invalid runId to NotFoundPage", async () => {
    sessionStorage.setItem(API_KEY_STORAGE_KEY, "my-valid-api-key");
    renderWithProviders("/audits/not-a-number");

    expect(await screen.findByText(/404 – không tìm thấy trang/i)).toBeInTheDocument();
  });

  it("redirects negative runId to NotFoundPage", async () => {
    sessionStorage.setItem(API_KEY_STORAGE_KEY, "my-valid-api-key");
    renderWithProviders("/audits/-5");

    expect(await screen.findByText(/404 – không tìm thấy trang/i)).toBeInTheDocument();
  });
});
