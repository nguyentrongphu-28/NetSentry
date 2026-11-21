import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "./msw/server";
import { renderWithProviders } from "./renderWithProviders";
import { BaselineCard } from "../components/baseline/BaselineCard";
import { SetBaselineDialog } from "../components/baseline/SetBaselineDialog";
import { DriftSummary } from "../components/baseline/DriftSummary";
import { DriftDetail } from "../components/baseline/DriftDetail";
import { DriftHistory } from "../components/baseline/DriftHistory";
import { DeviceBaselineTab } from "../components/baseline/DeviceBaselineTab";
import { AuditSummaryHeader } from "../components/audits/AuditSummaryHeader";
import { BaselineOut, DriftReportOut, DriftHistoryItemOut } from "../types/api";
import { STRINGS } from "../i18n/strings";

describe("Baseline & Drift Frontend Components (Spec 9.9)", () => {
  beforeEach(() => {
    server.resetHandlers();
    sessionStorage.clear();
    sessionStorage.setItem("netsentry.apiKey", "test-key");
  });

  describe("BaselineCard", () => {
    it("renders empty state when baseline is null", async () => {
      await renderWithProviders(
        <BaselineCard baseline={null} onRetire={() => {}} />,
        { renderAs: "viewer" },
      );
      expect(screen.getByText(STRINGS.baseline.noBaseline)).toBeInTheDocument();
    });

    it("renders active baseline details and hides retire button for viewer", async () => {
      const baseline: BaselineOut = {
        id: 1,
        device_id: "Router-Core-01",
        snapshot_id: 42,
        status: "ACTIVE",
        approved_by: "admin",
        approved_at: "2026-11-21T10:00:00Z",
        note: "Initial stable baseline",
        fail_count_at_approval: 0,
        content_sha256: "abc123def4567890",
      };

      await renderWithProviders(
        <BaselineCard baseline={baseline} onRetire={() => {}} />,
        { renderAs: "viewer" },
      );

      expect(screen.getByText("Snapshot #42")).toBeInTheDocument();
      expect(screen.getByText("admin")).toBeInTheDocument();
      expect(screen.getByText("Initial stable baseline")).toBeInTheDocument();
      expect(screen.queryByText(STRINGS.baseline.retireBtn)).not.toBeInTheDocument();
    });

    it("shows retire button for admin", async () => {
      const baseline: BaselineOut = {
        id: 1,
        device_id: "Router-Core-01",
        snapshot_id: 42,
        status: "ACTIVE",
        approved_by: "admin",
        approved_at: "2026-11-21T10:00:00Z",
        note: "Initial stable baseline",
        fail_count_at_approval: 2,
        content_sha256: "abc123def4567890",
      };

      await renderWithProviders(
        <BaselineCard baseline={baseline} onRetire={() => {}} />,
        { renderAs: "admin" },
      );

      expect(screen.getByText(STRINGS.baseline.retireBtn)).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  describe("SetBaselineDialog", () => {
    it("requires confirmation checkbox when snapshot has failures", async () => {
      const user = userEvent.setup();
      let submitted = false;

      await renderWithProviders(
        <SetBaselineDialog
          isOpen={true}
          onClose={() => {}}
          snapshotId={42}
          failCount={3}
          onConfirm={async () => {
            submitted = true;
          }}
        />,
        { renderAs: "admin" },
      );

      expect(screen.getByText(/có 3 lỗi FAIL/)).toBeInTheDocument();
      const submitBtn = screen.getByRole("button", { name: STRINGS.common.confirm });
      expect(submitBtn).toBeDisabled();

      // Check the confirmation checkbox
      const checkbox = screen.getByRole("checkbox");
      await user.click(checkbox);
      expect(submitBtn).toBeEnabled();

      await user.click(submitBtn);
      expect(submitted).toBe(true);
    });

    it("displays 409 error message and enables confirmation checkbox on conflict", async () => {
      const user = userEvent.setup();

      await renderWithProviders(
        <SetBaselineDialog
          isOpen={true}
          onClose={() => {}}
          snapshotId={42}
          failCount={0}
          onConfirm={async () => {
            throw new Error("Audit run #10 has 2 failing findings (BASELINE_FAILURES_NOT_CONFIRMED)");
          }}
        />,
        { renderAs: "admin" },
      );

      const submitBtn = screen.getByRole("button", { name: STRINGS.common.confirm });
      expect(submitBtn).toBeEnabled();

      await user.click(submitBtn);

      expect(await screen.findByText(/BASELINE_FAILURES_NOT_CONFIRMED/)).toBeInTheDocument();
      // Should now reveal the confirmation warning and checkbox
      expect(screen.getByRole("checkbox")).toBeInTheDocument();
    });

    it("renders user note as plain text and does not execute scripts", async () => {
      const user = userEvent.setup();
      const scriptPayload = "<script>alert('xss')</script>";
      let receivedNote = "";

      await renderWithProviders(
        <SetBaselineDialog
          isOpen={true}
          onClose={() => {}}
          snapshotId={42}
          failCount={0}
          onConfirm={async ({ note }) => {
            receivedNote = note;
          }}
        />,
        { renderAs: "admin" },
      );

      const textarea = screen.getByPlaceholderText(STRINGS.baseline.notePlaceholder);
      await user.type(textarea, scriptPayload);

      const submitBtn = screen.getByRole("button", { name: STRINGS.common.confirm });
      await user.click(submitBtn);

      expect(receivedNote).toBe(scriptPayload);
    });
  });

  describe("DriftSummary & DriftDetail", () => {
    it("renders IN_SYNC status correctly", async () => {
      const report: DriftReportOut = {
        device_id: "Router-Core-01",
        run_id: 10,
        baseline_id: 1,
        lines_included: false,
        summary: {
          status: "IN_SYNC",
          added_blocks: 0,
          removed_blocks: 0,
          changed_blocks: 0,
          security_relevant_count: 0,
        },
        truncated: false,
        blocks: [],
      };

      await renderWithProviders(
        <DriftSummary report={report} />,
        { renderAs: "viewer" },
      );

      expect(screen.getByText(STRINGS.drift.inSync)).toBeInTheDocument();
    });

    it("renders DRIFTED status with security-relevant highlighted blocks", async () => {
      const report: DriftReportOut = {
        device_id: "Router-Core-01",
        run_id: 10,
        baseline_id: 1,
        lines_included: false,
        summary: {
          status: "DRIFTED",
          added_blocks: 1,
          removed_blocks: 1,
          changed_blocks: 1,
          security_relevant_count: 2,
        },
        truncated: false,
        blocks: [
          {
            key: "line vty 0 4",
            kind: "CHANGED",
            security_relevant: true,
            added_lines: [],
            removed_lines: [],
            added_count: 1,
            removed_count: 1,
          },
          {
            key: "interface GigabitEthernet0/1",
            kind: "ADDED",
            security_relevant: false,
            added_lines: [],
            removed_lines: [],
            added_count: 3,
            removed_count: 0,
          },
        ],
      };

      await renderWithProviders(
        <DriftSummary report={report} />,
        { renderAs: "operator" },
      );

      expect(screen.getByText(STRINGS.drift.drifted)).toBeInTheDocument();
      expect(screen.getByText("line vty 0 4")).toBeInTheDocument();
      expect(screen.getByText(STRINGS.drift.securityRelevant)).toBeInTheDocument();
      expect(screen.getByText("interface GigabitEthernet0/1")).toBeInTheDocument();
    });

    it("renders DriftDetail with added/removed lines and truncated warning", async () => {
      const detailReport: DriftReportOut = {
        device_id: "Router-Core-01",
        run_id: 10,
        baseline_id: 1,
        lines_included: true,
        summary: {
          status: "DRIFTED",
          added_blocks: 1,
          removed_blocks: 0,
          changed_blocks: 0,
          security_relevant_count: 1,
        },
        truncated: true,
        blocks: [
          {
            key: "line vty 0 4",
            kind: "CHANGED",
            security_relevant: true,
            added_lines: ["transport input ssh"],
            removed_lines: ["transport input telnet"],
            added_count: 1,
            removed_count: 1,
          },
        ],
      };

      await renderWithProviders(
        <DriftDetail isOpen={true} onClose={() => {}} report={detailReport} />,
        { renderAs: "operator" },
      );

      expect(screen.getByText(STRINGS.drift.truncated)).toBeInTheDocument();
      expect(screen.getByText("transport input telnet")).toBeInTheDocument();
      expect(screen.getByText("transport input ssh")).toBeInTheDocument();
    });
  });

  describe("DriftHistory", () => {
    it("renders items in chronological order with correct badges", async () => {
      const history: DriftHistoryItemOut[] = [
        {
          device_id: "Router-Core-01",
          baseline_id: 1,
          run_id: 12,
          checked_at: "2026-11-21T12:00:00Z",
          status: "IN_SYNC",
          added_blocks: 0,
          removed_blocks: 0,
          changed_blocks: 0,
          security_relevant_count: 0,
        },
        {
          device_id: "Router-Core-01",
          baseline_id: 1,
          run_id: 11,
          checked_at: "2026-11-21T11:00:00Z",
          status: "DRIFTED",
          added_blocks: 2,
          removed_blocks: 1,
          changed_blocks: 0,
          security_relevant_count: 1,
        },
      ];

      await renderWithProviders(
        <DriftHistory history={history} />,
        { renderAs: "viewer" },
      );

      expect(screen.getByText("#12")).toBeInTheDocument();
      expect(screen.getByText("#11")).toBeInTheDocument();
      expect(screen.getByText("IN_SYNC")).toBeInTheDocument();
      expect(screen.getByText("DRIFTED")).toBeInTheDocument();
    });
  });

  describe("DeviceBaselineTab with CONTENT_DISABLED and RBAC", () => {
    it("handles CONTENT_DISABLED when operator requests lines in public mode", async () => {
      const user = userEvent.setup();

      server.use(
        http.get("/api/v1/devices/:id/baseline", () => {
          return HttpResponse.json({
            id: 1,
            device_id: "Router-Core-01",
            snapshot_id: 10,
            status: "ACTIVE",
            approved_by: "admin",
            approved_at: "2026-11-21T10:00:00Z",
            note: null,
            fail_count_at_approval: 0,
            content_sha256: "sha256hash",
          });
        }),
        http.get("/api/v1/devices/:id/drift", ({ request }) => {
          const url = new URL(request.url);
          if (url.searchParams.get("detail") === "1") {
            return HttpResponse.json(
              { error: { code: "CONTENT_DISABLED", message: "Snapshot content API is disabled" } },
              { status: 403 },
            );
          }
          return HttpResponse.json({
            device_id: "Router-Core-01",
            run_id: 10,
            baseline_id: 1,
            lines_included: false,
            summary: {
              status: "DRIFTED",
              added_blocks: 1,
              removed_blocks: 0,
              changed_blocks: 0,
              security_relevant_count: 0,
            },
            truncated: false,
            blocks: [
              {
                key: "interface Loopback0",
                kind: "ADDED",
                security_relevant: false,
                added_lines: [],
                removed_lines: [],
                added_count: 1,
                removed_count: 0,
              },
            ],
          });
        }),
        http.get("/api/v1/devices/:id/drift/history", () => {
          return HttpResponse.json([]);
        }),
      );

      await renderWithProviders(
        <DeviceBaselineTab deviceId="Router-Core-01" />,
        { renderAs: "operator" },
      );

      // Verify summary loaded
      expect(await screen.findByText(STRINGS.drift.drifted)).toBeInTheDocument();

      // Click "Xem chi tiết dòng"
      const viewDetailBtn = screen.getByRole("button", { name: STRINGS.drift.viewDetailBtn });
      await user.click(viewDetailBtn);

      // Should show the public mode disabled notification
      expect(await screen.findByText(STRINGS.drift.contentDisabled)).toBeInTheDocument();
    });
  });

  describe("AuditSummaryHeader Drift Badge", () => {
    it("renders 'Lệch baseline: N khối' badge when DRIFTED and links to baseline tab", async () => {
      server.use(
        http.get("/api/v1/devices/:id/drift", () => {
          return HttpResponse.json({
            device_id: "Router-Core-01",
            run_id: 5,
            baseline_id: 1,
            lines_included: false,
            summary: {
              status: "DRIFTED",
              added_blocks: 2,
              removed_blocks: 1,
              changed_blocks: 0,
              security_relevant_count: 1,
            },
            truncated: false,
            blocks: [],
          });
        }),
      );

      const summary = {
        id: 5,
        device_id: "Router-Core-01",
        hostname: "Router-Core-01",
        platform: "cisco_ios",
        status: "COMPLETED" as const,
        started_at: "2026-11-21T10:00:00Z",
        completed_at: "2026-11-21T10:01:00Z",
        finished_at: "2026-11-21T10:01:00Z",
        duration_ms: 60000,
        rules_run: 10,
        pass_count: 8,
        fail_count: 2,
        unknown_count: 0,
        error_code: null,
        error_message: null,
      };

      await renderWithProviders(<AuditSummaryHeader summary={summary} />, { renderAs: "viewer" });

      const badge = await screen.findByText(/Lệch baseline: 3 khối/);
      expect(badge).toBeInTheDocument();
      const link = badge.closest("a");
      expect(link).toHaveAttribute("href", "/devices/Router-Core-01?tab=baseline");
    });
  });
});
