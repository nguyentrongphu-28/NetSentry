import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/msw/server";
import { AuditRunPage } from "./AuditRunPage";
import { mockAuditRunDetail, mockAuditSummaryFailed } from "../test/fixtures";
import { FindingOut } from "../types/api";

function renderAuditRunPage(runId = "101") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/audits/${runId}`]}>
        <Routes>
          <Route path="/audits/:runId" element={<AuditRunPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AuditRunPage and FindingsTable Features (Section 7.6)", () => {
  beforeEach(() => {
    server.resetHandlers();
    sessionStorage.clear();
    sessionStorage.setItem("netsentry.apiKey", "test-key");
  });

  it("renders audit summary header and findings in default sort order (FAIL > UNKNOWN > PASS)", async () => {
    renderAuditRunPage("101");

    expect(await screen.findByText("Lượt kiểm toán #101")).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Router-Core-01/i })).toBeInTheDocument();

    // Findings are sorted: FAIL (CISCO-TELNET-01) -> UNKNOWN (CISCO-SNMP-01) -> PASS (CISCO-PASS-01)
    const ruleButtons = screen.getAllByRole("button", { expanded: false });
    expect(ruleButtons.length).toBe(3);

    expect(within(ruleButtons[0]!).getByText("CISCO-TELNET-01")).toBeInTheDocument();
    expect(within(ruleButtons[1]!).getByText("CISCO-SNMP-01")).toBeInTheDocument();
    expect(within(ruleButtons[2]!).getByText("CISCO-PASS-01")).toBeInTheDocument();
  });

  it("filters findings by status and severity correctly", async () => {
    const user = userEvent.setup();
    renderAuditRunPage("101");

    await screen.findByText("Lượt kiểm toán #101");

    const statusSelect = screen.getByLabelText(/lọc trạng thái/i);
    const severitySelect = screen.getByLabelText(/lọc mức độ/i);

    // Filter status = FAIL
    await user.selectOptions(statusSelect, "FAIL");
    expect(screen.getByText("CISCO-TELNET-01")).toBeInTheDocument();
    expect(screen.queryByText("CISCO-PASS-01")).not.toBeInTheDocument();
    expect(screen.queryByText("CISCO-SNMP-01")).not.toBeInTheDocument();

    // Filter severity = HIGH (should match none of the FAIL findings)
    await user.selectOptions(severitySelect, "HIGH");
    expect(
      screen.getByText("Không có finding nào phù hợp với bộ lọc hiện tại.")
    ).toBeInTheDocument();

    // Reset filters
    await user.selectOptions(statusSelect, "ALL");
    await user.selectOptions(severitySelect, "ALL");
    expect(screen.getByText("CISCO-TELNET-01")).toBeInTheDocument();
    expect(screen.getByText("CISCO-PASS-01")).toBeInTheDocument();
  });

  it("expands a finding row, verifies aria-expanded and copies remediation text", async () => {
    const user = userEvent.setup();
    const clipboardWriteSpy = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined);
    renderAuditRunPage("101");

    await screen.findByText("Lượt kiểm toán #101");

    const telnetRow = screen.getByRole("button", { name: /CISCO-TELNET-01/i });
    expect(telnetRow).toHaveAttribute("aria-expanded", "false");

    // Click to expand
    await user.click(telnetRow);
    expect(telnetRow).toHaveAttribute("aria-expanded", "true");

    // Check evidence and rationale
    expect(screen.getByText("Telnet sends credentials in plain text.")).toBeInTheDocument();
    expect(screen.getByText('line vty 0 4')).toBeInTheDocument();
    expect(screen.getByText('transport input telnet ssh')).toBeInTheDocument();
    expect(
      screen.getByText(/Đây chỉ là hướng dẫn. NetSentry không tự thay đổi cấu hình thiết bị./)
    ).toBeInTheDocument();

    // Copy remediation button
    const copyBtn = screen.getByRole("button", { name: "Sao chép lệnh" });
    await user.click(copyBtn);

    expect(clipboardWriteSpy).toHaveBeenCalledWith(
      "configure terminal\nline vty 0 4\ntransport input ssh"
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Đã chép!");
  });

  it("prevents XSS: raw HTML or scripts in findings are escaped and rendered as text", async () => {
    const xssFinding: FindingOut = {
      rule_id: "XSS-TEST-01",
      title: "<script>alert('xss')</script> Injection Title",
      severity: "CRITICAL",
      status: "FAIL",
      evidence: ["<img src=x onerror=alert('xss')>", "system script injected"],
      rationale: "<b>Bold Rationale</b> without HTML execution",
      remediation: "<script>dangerous_code()</script>",
      verification: "verify <tag>",
    };

    server.use(
      http.get("/api/v1/audits/101", () => {
        return HttpResponse.json({
          ...mockAuditRunDetail,
          findings: [xssFinding],
        });
      })
    );

    const user = userEvent.setup();
    renderAuditRunPage("101");

    await screen.findByText("Lượt kiểm toán #101");

    // Title should be visible as raw text, no script executed
    expect(
      screen.getByText("<script>alert('xss')</script> Injection Title")
    ).toBeInTheDocument();
    expect(document.querySelector("script[src]")).toBeNull();

    // Expand row and verify evidence is plain text
    const rowBtn = screen.getByRole("button", { name: /XSS-TEST-01/i });
    await user.click(rowBtn);

    expect(
      screen.getByText(/<img src=x onerror=alert\('xss'\)>/)
    ).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });

  it("displays prominent error block and NO findings table when run is FAILED", async () => {
    server.use(
      http.get("/api/v1/audits/102", () => {
        return HttpResponse.json({
          summary: mockAuditSummaryFailed,
          findings: [],
        });
      })
    );

    renderAuditRunPage("102");

    expect(await screen.findByText("Lượt kiểm toán #102")).toBeInTheDocument();
    expect(
      screen.getByText("Kiểm toán thất bại do lỗi kết nối / xác thực")
    ).toBeInTheDocument();
    expect(screen.getByText("AUTH_FAILED")).toBeInTheDocument();
    expect(
      screen.getByText(/Sai tên đăng nhập, mật khẩu hoặc enable secret./)
    ).toBeInTheDocument();

    // Findings table header must NOT be present
    expect(
      screen.queryByText("Danh sách phát hiện (Findings)")
    ).not.toBeInTheDocument();
  });
});
