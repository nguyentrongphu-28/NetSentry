import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { AuthProvider } from "../auth/AuthProvider";
import { server } from "./msw/server";

export type TestRole = "viewer" | "operator" | "admin";

export interface RenderOptions {
  route?: string;
  /** Role returned by GET /api/v1/auth/me. Use null to simulate a logged-out visitor. */
  renderAs?: TestRole | null;
  bodyCredentials?: boolean;
  mustChangePassword?: boolean;
}

export async function renderWithProviders(
  ui: ReactElement,
  {
    route = "/",
    renderAs = "viewer",
    bodyCredentials = false,
    mustChangePassword = false,
  }: RenderOptions = {},
) {
  server.use(
    http.get("/api/v1/auth/me", () => {
      if (renderAs === null) {
        return HttpResponse.json(
          { error: { code: "UNAUTHORIZED", message: "Authentication required" } },
          { status: 401 },
        );
      }
      return HttpResponse.json({
        user: {
          id: 1,
          username: `test-${renderAs}`,
          role: renderAs,
          must_change_password: mustChangePassword,
        },
        capabilities: { body_credentials: bodyCredentials },
      });
    }),
  );

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  const result = render(
    <MemoryRouter initialEntries={[route]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{ui}</AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );

  await screen.findByTestId("auth-ready");
  return { ...result, queryClient };
}
