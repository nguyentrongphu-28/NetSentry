import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import App from "../App";
import { server } from "./msw/server";

describe("Smoke test", () => {
  beforeEach(() => {
    server.resetHandlers();
    window.history.pushState({}, "", "/");
  });

  it("shows the login screen for a logged-out visitor", async () => {
    server.use(
      http.get("/api/v1/auth/me", () =>
        HttpResponse.json(
          { error: { code: "UNAUTHORIZED", message: "Authentication required" } },
          { status: 401 },
        ),
      ),
    );

    render(<App />);

    expect(await screen.findByRole("button", { name: /đăng nhập/i })).toBeInTheDocument();
  });

  it("shows the dashboard for a logged-in operator", async () => {
    server.use(
      http.get("/api/v1/auth/me", () =>
        HttpResponse.json({
          user: { id: 1, username: "test-operator", role: "operator", must_change_password: false },
          capabilities: { body_credentials: false },
        }),
      ),
    );

    render(<App />);

    expect(await screen.findByText("Danh sách thiết bị")).toBeInTheDocument();
  });
});
