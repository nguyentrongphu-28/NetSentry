import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/msw/server";
import { DeviceDetailPage } from "./DeviceDetailPage";
import { mockAuditSummaryCompleted } from "../test/fixtures";

function renderDeviceDetailPage(deviceId = "Router-Core-01") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/devices/${deviceId}`]}>
        <Routes>
          <Route path="/devices/:deviceId" element={<DeviceDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("DeviceDetailPage and AuditHistoryTable Features (Section 7.7)", () => {
  beforeEach(() => {
    server.resetHandlers();
    sessionStorage.clear();
    sessionStorage.setItem("netsentry.apiKey", "test-key");
  });

  it("renders device details and latest audit summary correctly", async () => {
    renderDeviceDetailPage("Router-Core-01");

    expect(await screen.findByRole("heading", { name: "Router-Core-01" })).toBeInTheDocument();
    expect(screen.getByText("Core Router 01")).toBeInTheDocument();
    expect(screen.getByText("192.168.1.1")).toBeInTheDocument();
    expect(screen.getByText("22")).toBeInTheDocument();

    // Latest audit summary
    expect(screen.getByText("Lần kiểm toán gần nhất")).toBeInTheDocument();
    expect(screen.getByText("Xem chi tiết lần audit #101 →")).toBeInTheDocument();
  });

  it("displays paginated audit history with limit, offset, total and boundary controls", async () => {
    // Return 25 items across 2 pages (limit 20)
    const mockItems = Array.from({ length: 25 }, (_, i) => ({
      ...mockAuditSummaryCompleted,
      id: 1000 + i,
      started_at: `2026-11-18T08:${String(i).padStart(2, "0")}:00Z`,
    }));

    server.use(
      http.get("/api/v1/devices/:deviceId/audits", ({ request }) => {
        const url = new URL(request.url);
        const limit = Number(url.searchParams.get("limit") || 20);
        const offset = Number(url.searchParams.get("offset") || 0);

        return HttpResponse.json({
          items: mockItems.slice(offset, offset + limit),
          total: 25,
          limit,
          offset,
        });
      })
    );

    const user = userEvent.setup();
    renderDeviceDetailPage("Router-Core-01");

    // Page 1: 1-20 of 25
    expect(await screen.findByText(/1–20/)).toBeInTheDocument();
    expect(screen.getByText(/25/)).toBeInTheDocument();

    const prevBtn = screen.getByRole("button", { name: /Trước/i });
    const nextBtn = screen.getByRole("button", { name: /Sau/i });

    // On page 1: Prev is disabled, Next is enabled
    expect(prevBtn).toBeDisabled();
    expect(nextBtn).toBeEnabled();

    // Navigate to next page
    await user.click(nextBtn);

    // Page 2: 21-25 of 25
    expect(await screen.findByText(/21–25/)).toBeInTheDocument();

    // On page 2 (last page): Next is disabled, Prev is enabled
    expect(nextBtn).toBeDisabled();
    expect(prevBtn).toBeEnabled();

    // Navigate back to page 1
    await user.click(prevBtn);
    expect(await screen.findByText(/1–20/)).toBeInTheDocument();
    expect(prevBtn).toBeDisabled();
  });

  it("renders empty state when device has no previous audit history", async () => {
    server.use(
      http.get("/api/v1/devices/:deviceId/audits", () => {
        return HttpResponse.json({
          items: [],
          total: 0,
          limit: 20,
          offset: 0,
        });
      })
    );

    renderDeviceDetailPage("Router-Core-01");

    expect(
      await screen.findByText("Thiết bị này chưa từng được audit.")
    ).toBeInTheDocument();
  });
});
