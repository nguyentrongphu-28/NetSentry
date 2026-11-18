import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/msw/server";
import { DevicesPage } from "./DevicesPage";

function renderDevicesPage(): ReturnType<typeof render> {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DevicesPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("DevicesPage and Dashboard Features (Section 7.3 - 7.4)", () => {
  beforeEach(() => {
    server.resetHandlers();
    sessionStorage.setItem("netsentry.apiKey", "valid-test-key");
  });

  it("calculates and displays summary tiles correctly from sample devices", async () => {
    renderDevicesPage();

    // Wait for data to load
    expect(await screen.findByText("Router-Core-01")).toBeInTheDocument();

    expect(screen.getByText("Tổng số thiết bị")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // Total devices

    // "Chưa audit" appears in tile and table row
    expect(screen.getAllByText("Chưa audit").length).toBeGreaterThanOrEqual(1);
    // 3 tiles have value 1: unaudited, failedAudits, devicesWithFailFindings
    expect(screen.getAllByText("1")).toHaveLength(3);

    expect(screen.getByText("Lỗi kết nối (FAILED)")).toBeInTheDocument();
    expect(screen.getByText("Thiết bị có rủi ro")).toBeInTheDocument();
    expect(screen.getByText("Tổng finding FAIL")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // Total fails
  });

  it("displays empty state when device list is empty", async () => {
    server.use(
      http.get("/api/v1/devices", () => {
        return HttpResponse.json({ items: [] });
      })
    );

    renderDevicesPage();
    expect(await screen.findByText("Chưa có thiết bị nào")).toBeInTheDocument();
    expect(screen.getByText("Thêm thiết bị mới")).toBeInTheDocument();
  });

  it("displays error banner with retry button on API failure", async () => {
    server.use(
      http.get("/api/v1/devices", () => {
        return HttpResponse.error();
      })
    );

    renderDevicesPage();
    expect(await screen.findByText(/không thể tải danh sách thiết bị/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /thử lại/i })).toBeInTheDocument();
  });

  it("validates client fields and creates new device successfully", async () => {
  const user = userEvent.setup();
  renderDevicesPage();

  await screen.findByText("Router-Core-01");

  // Click header "Thêm thiết bị" button
  const openAddBtn = screen.getByRole("button", { name: "Thêm thiết bị" });
  await user.click(openAddBtn);

  // Dialog appears
  const dialog = screen.getByRole("dialog");
  expect(dialog).toBeInTheDocument();
  expect(within(dialog).getByText("Thêm thiết bị mới")).toBeInTheDocument();

  // Submit button inside dialog
  const submitBtn = within(dialog).getByRole("button", { name: "Thêm thiết bị" });
  await user.click(submitBtn);

  expect(await within(dialog).findByText("Vui lòng nhập mã thiết bị.")).toBeInTheDocument();

  // Fill valid data
  const idInput = within(dialog).getByLabelText(/mã thiết bị/i);
  const hostInput = within(dialog).getByLabelText(/địa chỉ ip/i);

  await user.type(idInput, "Router-Lab-99");
  await user.type(hostInput, "10.0.0.1");

  await user.click(submitBtn);

    // Modal closes on success
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  }, 10000);

  it("displays server error 409 DEVICE_EXISTS next to device_id field", async () => {
    const user = userEvent.setup();
    renderDevicesPage();

    await screen.findByText("Router-Core-01");

    await user.click(screen.getByRole("button", { name: "Thêm thiết bị" }));
    const dialog = screen.getByRole("dialog");

    const idInput = within(dialog).getByLabelText(/mã thiết bị/i);
    const hostInput = within(dialog).getByLabelText(/địa chỉ ip/i);

    fireEvent.change(idInput, { target: { value: "existing-device" } });
    fireEvent.change(hostInput, { target: { value: "10.0.0.1" } });

    await user.click(within(dialog).getByRole("button", { name: "Thêm thiết bị" }));

    expect(
      await within(dialog).findByText("Thiết bị với ID này đã tồn tại trên hệ thống.")
    ).toBeInTheDocument();
  });

  it("displays loading spinner while fetching devices", async () => {
    server.use(
      http.get("/api/v1/devices", async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json({ items: [] });
      })
    );

    renderDevicesPage();
    expect(screen.getByText("Đang tải danh sách thiết bị...")).toBeInTheDocument();
  });

  it("displays server error 422 VALIDATION_ERROR next to fields", async () => {
    server.use(
      http.post("/api/v1/devices", () => {
        return HttpResponse.json(
          {
            error: {
              code: "VALIDATION_ERROR",
              message: "Dữ liệu không hợp lệ.",
              details: [
                { field: "host", message: "Địa chỉ IP không thể phân giải." },
              ],
            },
          },
          { status: 422 }
        );
      })
    );

    const user = userEvent.setup();
    renderDevicesPage();

    await screen.findByText("Router-Core-01");

    await user.click(screen.getByRole("button", { name: "Thêm thiết bị" }));
    const dialog = screen.getByRole("dialog");

    const idInput = within(dialog).getByLabelText(/mã thiết bị/i);
    const hostInput = within(dialog).getByLabelText(/địa chỉ ip/i);

    fireEvent.change(idInput, { target: { value: "New-Router-01" } });
    fireEvent.change(hostInput, { target: { value: "invalid.domain.xyz" } });

    await user.click(within(dialog).getByRole("button", { name: "Thêm thiết bị" }));

    expect(
      await within(dialog).findByText("Địa chỉ IP không thể phân giải.")
    ).toBeInTheDocument();
  });

  it("opens delete dialog and deletes device successfully", async () => {
    const user = userEvent.setup();
    renderDevicesPage();

    await screen.findByText("Router-Core-01");

    // Click delete icon for Router-Core-01
    const deleteBtn = screen.getByLabelText("Xóa Router-Core-01");
    await user.click(deleteBtn);

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Xác nhận xóa thiết bị")).toBeInTheDocument();
    expect(within(dialog).getByText(/lịch sử audit liên quan/i)).toBeInTheDocument();

    // Confirm deletion
    const confirmBtn = within(dialog).getByRole("button", { name: "Xóa thiết bị" });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
