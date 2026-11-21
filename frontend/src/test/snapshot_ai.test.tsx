import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "./msw/server";
import { renderWithProviders } from "./renderWithProviders";
import { ComparePanel } from "../components/audits/ComparePanel";
import { AiExplainPanel } from "../components/audits/AiExplainPanel";
import { DiffViewer } from "../components/devices/DiffViewer";
import { SnapshotList } from "../components/devices/SnapshotList";
import { ConfigDiffOut } from "../types/api";

describe("Snapshot, Compare & AI Components (Spec 10.13)", () => {
  beforeEach(() => {
    server.resetHandlers();
    sessionStorage.clear();
    sessionStorage.setItem("netsentry.apiKey", "test-key");
  });

  describe("ComparePanel", () => {
    it("renders no-previous message when has_previous is false", async () => {
      server.use(
        http.get("/api/v1/audits/:runId/compare", () => {
          return HttpResponse.json({
            from_run_id: null,
            to_run_id: 101,
            device_id: "Router-Core-01",
            has_previous: false,
            changes: [],
            counts: {},
          });
        }),
      );

      await renderWithProviders(<ComparePanel runId={101} />, { renderAs: "operator" });

      expect(await screen.findByText("Chưa có lần audit trước để so sánh.")).toBeInTheDocument();
    });

    it("renders regression, fixed, and persisting change groups", async () => {
      server.use(
        http.get("/api/v1/audits/:runId/compare", () => {
          return HttpResponse.json({
            from_run_id: 100,
            to_run_id: 101,
            device_id: "Router-Core-01",
            has_previous: true,
            changes: [
              {
                rule_id: "CISCO-TELNET-01",
                title: "Telnet Service Enabled",
                before_status: "PASS",
                after_status: "FAIL",
                after_severity: "HIGH",
                kind: "REGRESSION",
              },
              {
                rule_id: "CISCO-SNMP-01",
                title: "Insecure SNMP Community",
                before_status: "FAIL",
                after_status: "PASS",
                after_severity: "MEDIUM",
                kind: "FIXED",
              },
              {
                rule_id: "CISCO-SSH-01",
                title: "SSH v1 Enabled",
                before_status: "FAIL",
                after_status: "FAIL",
                after_severity: "CRITICAL",
                kind: "PERSISTING",
              },
            ],
            counts: { REGRESSION: 1, FIXED: 1, PERSISTING: 1 },
          });
        }),
      );

      await renderWithProviders(<ComparePanel runId={101} />, { renderAs: "operator" });

      expect(await screen.findByText(/Audit #101 vs #100/)).toBeInTheDocument();
      expect(screen.getByText("CISCO-TELNET-01")).toBeInTheDocument();
      expect(screen.getByText("CISCO-SNMP-01")).toBeInTheDocument();
      expect(screen.getByText("CISCO-SSH-01")).toBeInTheDocument();
    });
  });

  describe("AiExplainPanel", () => {
    it("viewer does not see explain button", async () => {
      server.use(
        http.get("/api/v1/ai/status", () => {
          return HttpResponse.json({
            enabled: true,
            reachable: true,
            model: "llama3:8b",
          });
        }),
        http.get("/api/v1/audits/:runId/explanation", () => {
          return HttpResponse.json(
            { error: { code: "NOT_FOUND", message: "Not generated yet" } },
            { status: 404 },
          );
        }),
      );

      await renderWithProviders(<AiExplainPanel runId={101} />, { renderAs: "viewer" });

      expect(await screen.findByText("Phân tích AI")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Giải thích bằng AI/i })).not.toBeInTheDocument();
    });

    it("operator sees explain button, clicks, gets explanation with disclaimer and escapes XSS", async () => {
      const user = userEvent.setup();
      server.use(
        http.get("/api/v1/ai/status", () => {
          return HttpResponse.json({
            enabled: true,
            reachable: true,
            model: "llama3:8b",
          });
        }),
        http.get("/api/v1/audits/:runId/explanation", () => {
          return HttpResponse.json(
            { error: { code: "NOT_FOUND", message: "Not generated yet" } },
            { status: 404 },
          );
        }),
        http.post("/api/v1/audits/:runId/explain", () => {
          return HttpResponse.json({
            run_id: 101,
            created_at: new Date().toISOString(),
            model: "llama3:8b",
            prompt_version: 1,
            input_sha256: "abc123",
            summary: "Cần chú ý <script>alert('xss')</script> an ninh.",
            priorities: [{ rule_id: "CISCO-TELNET-01", reason: "Nguy cơ lộ mật khẩu rõ" }],
            risks: [{ rule_id: "CISCO-SSH-01", warning: "Mất kết nối quản trị tạm thời" }],
            generated_by_ai: true,
          });
        }),
      );

      await renderWithProviders(<AiExplainPanel runId={101} />, { renderAs: "operator" });

      const explainBtn = await screen.findByRole("button", { name: /Giải thích bằng AI/i });
      expect(explainBtn).toBeInTheDocument();

      await user.click(explainBtn);

      expect(await screen.findByText(/Cần chú ý <script>alert\('xss'\)<\/script> an ninh\./)).toBeInTheDocument();
      expect(screen.getByText(/Nội dung do AI sinh ra, chỉ mang tính tham khảo/)).toBeInTheDocument();
      expect(screen.getByText("CISCO-TELNET-01:")).toBeInTheDocument();
      expect(screen.getByText("Nguy cơ lộ mật khẩu rõ")).toBeInTheDocument();
    });
  });

  describe("DiffViewer", () => {
    it("renders identical config message", async () => {
      const mockDiff: ConfigDiffOut = {
        from_run_id: 100,
        to_run_id: 101,
        identical: true,
        added: 0,
        removed: 0,
        hunks: [],
        truncated: false,
      };

      await renderWithProviders(<DiffViewer diff={mockDiff} />);
      expect(screen.getByText("Hai bản cấu hình hoàn toàn giống nhau.")).toBeInTheDocument();
    });

    it("renders hunks and truncated warning", async () => {
      const mockDiff: ConfigDiffOut = {
        from_run_id: 100,
        to_run_id: 101,
        identical: false,
        added: 1,
        removed: 1,
        hunks: [
          {
            old_start: 10,
            new_start: 10,
            lines: [
              { op: "-", text: "no service password-encryption" },
              { op: "+", text: "service password-encryption" },
            ],
          },
        ],
        truncated: true,
      };

      await renderWithProviders(<DiffViewer diff={mockDiff} />);

      expect(screen.getByText(/Kết quả diff quá dài/)).toBeInTheDocument();
      expect(screen.getByText("no service password-encryption")).toBeInTheDocument();
      expect(screen.getByText("service password-encryption")).toBeInTheDocument();
    });
  });

  describe("SnapshotList", () => {
    it("shows empty message when no snapshots exist", async () => {
      server.use(
        http.get("/api/v1/devices/:deviceId/snapshots", () => {
          return HttpResponse.json([]);
        }),
      );

      await renderWithProviders(<SnapshotList deviceId="Router-Core-01" />, { renderAs: "operator" });

      expect(await screen.findByText("Chưa có bản snapshot cấu hình nào.")).toBeInTheDocument();
    });
  });
});
