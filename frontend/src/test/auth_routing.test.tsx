import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { AppRoutes } from "../App";
import { server } from "./msw/server";
import { renderWithProviders } from "./renderWithProviders";

// NOTE: adjust the label regexes below to the real texts in LoginPage / ChangePasswordPage.
describe("Auth and routing", () => {
  it("redirects a logged-out visitor from / to /login", async () => {
    await renderWithProviders(<AppRoutes />, { route: "/", renderAs: null });
    expect(await screen.findByRole("button", { name: /đăng nhập/i })).toBeInTheDocument();
  });

  it("forces /change-password when must_change_password is set", async () => {
    await renderWithProviders(<AppRoutes />, {
      route: "/",
      renderAs: "operator",
      mustChangePassword: true,
    });
    expect(await screen.findByRole("heading", { name: /đổi mật khẩu/i })).toBeInTheDocument();
  });

  it("goes back to /login when an API call returns 401 mid-session", async () => {
    server.use(
      http.get("/api/v1/devices", () =>
        HttpResponse.json(
          { error: { code: "UNAUTHORIZED", message: "Authentication required" } },
          { status: 401 },
        ),
      ),
    );
    await renderWithProviders(<AppRoutes />, { route: "/", renderAs: "operator" });
    expect(await screen.findByRole("button", { name: /đăng nhập/i })).toBeInTheDocument();
  });

  it("does not show the users page to a viewer", async () => {
    await renderWithProviders(<AppRoutes />, { route: "/users", renderAs: "viewer" });
    await screen.findByTestId("auth-ready");
    expect(screen.queryByRole("heading", { name: /quản lý người dùng/i })).not.toBeInTheDocument();
  });

  it("shows NotFound for an invalid runId", async () => {
    await renderWithProviders(<AppRoutes />, { route: "/audits/not-a-number", renderAs: "operator" });
    expect(await screen.findByText(/404 – không tìm thấy trang/i)).toBeInTheDocument();
  });

  it("shows NotFound for a negative runId", async () => {
    await renderWithProviders(<AppRoutes />, { route: "/audits/-5", renderAs: "operator" });
    expect(await screen.findByText(/404 – không tìm thấy trang/i)).toBeInTheDocument();
  });
});
