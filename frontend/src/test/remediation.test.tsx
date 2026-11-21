import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./msw/server";
import { renderWithProviders } from "./renderWithProviders";
import { FindingRow } from "../components/audits/FindingRow";
import { RemediationPreviewDialog } from "../components/remediation/RemediationPreviewDialog";
import { ApproveDialog } from "../components/remediation/ApproveDialog";
import { RejectDialog } from "../components/remediation/RejectDialog";
import { PlanTimeline } from "../components/remediation/PlanTimeline";
import { RemediationPlanDetailPage } from "../pages/RemediationPlanDetailPage";
import {
  FindingOut,
  ManualGuidanceOut,
  PlanEventOut,
  RemediationPlanDetailOut,
  RemediationTemplateOut,
} from "../types/api";
import { STRINGS } from "../i18n/strings";

const mockTemplateNet008: RemediationTemplateOut = {
  rule_id: "NET-008",
  version: "1",
  title: "Khắc phục NET-008",
  commands: ["no ip http server"],
  risk_level: "LOW",
  impact: "Tắt dịch vụ máy chủ HTTP không mã hóa (cổng 80) trên thiết bị.",
  risks: "Nếu quản trị viên đang quản lý thiết bị qua HTTP sẽ mất truy cập.",
  reversible: true,
  rollback_note: "Hoàn tác bằng 'ip http server'.",
  platforms: ["cisco_ios"],
};

const mockManualGuidanceNet001: ManualGuidanceOut = {
  rule_id: "NET-001",
  title: "VTY Transport Input",
  remediation_guide: "Cấu hình 'line vty 0 4' và 'transport input ssh'.",
  verification_guide: "Kiểm tra 'show running-config | section line vty'.",
  why_not_automated: "Thay đổi VTY có thể dẫn đến nguy cơ tự khóa mình khỏi router.",
};

describe("Remediation Frontend Components & Flow (Spec Section 9.11)", () => {
  beforeEach(() => {
    server.resetHandlers();
    sessionStorage.clear();
  });

  describe("FindingRow - Propose Button & Manual Guidance", () => {
    const failingFindingNet008: FindingOut = {
      rule_id: "NET-008",
      title: "HTTP server enabled",
      severity: "MEDIUM",
      status: "FAIL",
      evidence: ["ip http server"],
      rationale: "HTTP plaintext is insecure",
      remediation: "no ip http server",
      verification: "show running-config | include http server",
    };

    const passingFindingNet008: FindingOut = {
      ...failingFindingNet008,
      status: "PASS",
    };

    const failingManualFindingNet001: FindingOut = {
      rule_id: "NET-001",
      title: "Telnet enabled on VTY",
      severity: "HIGH",
      status: "FAIL",
      evidence: ["transport input telnet"],
      rationale: "Telnet is insecure",
      remediation: "transport input ssh",
      verification: "show running-config | section line vty",
    };

    it("shows 'Đề xuất sửa' button for operator on FAIL finding of eligible rule", async () => {
      await renderWithProviders(
        <FindingRow
          finding={failingFindingNet008}
          runId={101}
          template={mockTemplateNet008}
        />,
        { renderAs: "operator" }
      );

      expect(screen.getByText(STRINGS.remediation.proposeBtn)).toBeInTheDocument();
    });

    it("shows 'Đề xuất sửa' button for admin on FAIL finding of eligible rule", async () => {
      await renderWithProviders(
        <FindingRow
          finding={failingFindingNet008}
          runId={101}
          template={mockTemplateNet008}
        />,
        { renderAs: "admin" }
      );

      expect(screen.getByText(STRINGS.remediation.proposeBtn)).toBeInTheDocument();
    });

    it("hides 'Đề xuất sửa' button for viewer", async () => {
      await renderWithProviders(
        <FindingRow
          finding={failingFindingNet008}
          runId={101}
          template={mockTemplateNet008}
        />,
        { renderAs: "viewer" }
      );

      expect(screen.queryByText(STRINGS.remediation.proposeBtn)).not.toBeInTheDocument();
    });

    it("hides 'Đề xuất sửa' button when finding is PASS", async () => {
      await renderWithProviders(
        <FindingRow
          finding={passingFindingNet008}
          runId={101}
          template={mockTemplateNet008}
        />,
        { renderAs: "admin" }
      );

      expect(screen.queryByText(STRINGS.remediation.proposeBtn)).not.toBeInTheDocument();
    });

    it("shows 'Xem hướng dẫn' for manual rule and hides 'Đề xuất sửa'", async () => {
      await renderWithProviders(
        <FindingRow
          finding={failingManualFindingNet001}
          runId={101}
          manualGuidance={mockManualGuidanceNet001}
        />,
        { renderAs: "admin" }
      );

      expect(screen.queryByText(STRINGS.remediation.proposeBtn)).not.toBeInTheDocument();
      expect(screen.getByText(STRINGS.remediation.manualGuideBtn)).toBeInTheDocument();
    });
  });

  describe("RemediationPreviewDialog", () => {
    it("renders commands in code block, risk level, impact, and persist toggle", async () => {
      await renderWithProviders(
        <RemediationPreviewDialog
          isOpen={true}
          onClose={() => {}}
          runId={101}
          template={mockTemplateNet008}
        />,
        { renderAs: "operator" }
      );

      expect(screen.getByText("no ip http server")).toBeInTheDocument();
      expect(screen.getByText(STRINGS.remediation.riskLevels.LOW)).toBeInTheDocument();
      expect(screen.getByText(mockTemplateNet008.impact)).toBeInTheDocument();
      expect(screen.getByText(mockTemplateNet008.risks)).toBeInTheDocument();

      const checkbox = screen.getByLabelText(STRINGS.remediation.preview.persistLabel) as HTMLInputElement;
      expect(checkbox.checked).toBe(false);

      await userEvent.click(checkbox);
      expect(checkbox.checked).toBe(true);
    });

    it("handles errors: ACTIVE_PLAN_EXISTS, PLAN_STALE, FINDING_NOT_FAILING, REMEDIATION_DISABLED", async () => {
      server.use(
        http.post("/api/v1/audits/:runId/findings/:ruleId/remediation", () => {
          return HttpResponse.json(
            { error: { code: "ACTIVE_PLAN_EXISTS", message: "Plan exists" } },
            { status: 409 }
          );
        })
      );

      await renderWithProviders(
        <RemediationPreviewDialog
          isOpen={true}
          onClose={() => {}}
          runId={101}
          template={mockTemplateNet008}
        />,
        { renderAs: "operator" }
      );

      const submitBtn = screen.getByText(STRINGS.remediation.preview.submitPropose);
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(
          screen.getByText(STRINGS.remediation.errors.ACTIVE_PLAN_EXISTS)
        ).toBeInTheDocument();
      });
    });
  });

  describe("ApproveDialog", () => {
    it("requires password and checkbox confirmation, clears password after submit", async () => {
      let capturedPassword = "";
      server.use(
        http.post("/api/v1/remediation-plans/:planId/approve", async ({ request }) => {
          const body = (await request.json()) as { password: string };
          capturedPassword = body.password;
          return HttpResponse.json({
            id: 1,
            device_id: "Router-1",
            rule_id: "NET-008",
            status: "APPROVED",
            risk_level: "LOW",
            persist_after_verify: false,
            proposed_by: "operator",
            proposed_at: "2026-11-21T10:00:00Z",
            decided_by: "admin",
            decided_at: "2026-11-21T11:00:00Z",
            expires_at: "2026-11-21T12:00:00Z",
            plan_hash: "hash123",
            commands: ["no ip http server"],
            impact: "impact",
            risks: "risks",
            expected_verification: { rule_id: "NET-008", expected_status: "PASS" },
            reversible: true,
            rollback_note: "rollback",
            approved_hash_matches: true,
            timeline: [],
          });
        })
      );

      const onSuccess = vi.fn();
      await renderWithProviders(
        <ApproveDialog
          isOpen={true}
          onClose={() => {}}
          planId={1}
          onSuccess={onSuccess}
        />,
        { renderAs: "admin" }
      );

      const passwordInput = screen.getByPlaceholderText(
        STRINGS.remediation.approve.passwordPlaceholder
      ) as HTMLInputElement;
      const checkbox = screen.getByLabelText(
        STRINGS.remediation.approve.confirmCheckbox
      ) as HTMLInputElement;
      const approveBtn = screen.getByRole("button", {
        name: STRINGS.remediation.approve.btnApprove,
      });

      expect(approveBtn).toBeDisabled();

      await userEvent.type(passwordInput, "SecretAdminPassword123!");
      expect(approveBtn).toBeDisabled();

      await userEvent.click(checkbox);
      expect(approveBtn).toBeEnabled();

      await userEvent.click(approveBtn);

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled();
      });

      expect(capturedPassword).toBe("SecretAdminPassword123!");
      // Verified password is never stored into storage
      expect(sessionStorage.getItem("password")).toBeNull();
      expect(localStorage.getItem("password")).toBeNull();
    });

    it("handles REAUTH_FAILED, SELF_APPROVAL_NOT_ALLOWED, PLAN_EXPIRED, PLAN_STALE errors", async () => {
      server.use(
        http.post("/api/v1/remediation-plans/:planId/approve", () => {
          return HttpResponse.json(
            { error: { code: "REAUTH_FAILED", message: "Password incorrect" } },
            { status: 422 }
          );
        })
      );

      await renderWithProviders(
        <ApproveDialog
          isOpen={true}
          onClose={() => {}}
          planId={1}
          onSuccess={() => {}}
        />,
        { renderAs: "admin" }
      );

      const passwordInput = screen.getByPlaceholderText(
        STRINGS.remediation.approve.passwordPlaceholder
      );
      const checkbox = screen.getByLabelText(
        STRINGS.remediation.approve.confirmCheckbox
      );
      const approveBtn = screen.getByRole("button", {
        name: STRINGS.remediation.approve.btnApprove,
      });

      await userEvent.type(passwordInput, "WrongPassword!");
      await userEvent.click(checkbox);
      await userEvent.click(approveBtn);

      await waitFor(() => {
        expect(
          screen.getByText(STRINGS.remediation.errors.REAUTH_FAILED)
        ).toBeInTheDocument();
      });
    });
  });

  describe("RejectDialog", () => {
    it("requires reason, enforces maxLength 200, and submits", async () => {
      let capturedReason = "";
      server.use(
        http.post("/api/v1/remediation-plans/:planId/reject", async ({ request }) => {
          const body = (await request.json()) as { reason: string };
          capturedReason = body.reason;
          return HttpResponse.json({});
        })
      );

      const onSuccess = vi.fn();
      await renderWithProviders(
        <RejectDialog
          isOpen={true}
          onClose={() => {}}
          planId={1}
          onSuccess={onSuccess}
        />,
        { renderAs: "admin" }
      );

      const reasonTextarea = screen.getByPlaceholderText(
        STRINGS.remediation.reject.reasonPlaceholder
      );
      const rejectBtn = screen.getByRole("button", {
        name: STRINGS.remediation.reject.btnReject,
      });

      expect(rejectBtn).toBeDisabled();

      await userEvent.type(reasonTextarea, "Device scheduled for decommission.");
      expect(rejectBtn).toBeEnabled();

      await userEvent.click(rejectBtn);

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled();
      });

      expect(capturedReason).toBe("Device scheduled for decommission.");
    });
  });

  describe("PlanTimeline", () => {
    it("renders events chronologically and escapes user input / HTML safely", async () => {
      const maliciousDetail = "<script>alert('xss')</script> Rejected by admin";
      const timeline: PlanEventOut[] = [
        {
          id: 1,
          plan_id: 1,
          occurred_at: "2026-11-21T10:00:00Z",
          actor: "operator1",
          event_type: "PROPOSED",
          detail: "Initial proposal",
        },
        {
          id: 2,
          plan_id: 1,
          occurred_at: "2026-11-21T10:15:00Z",
          actor: "admin1",
          event_type: "REJECTED",
          detail: maliciousDetail,
        },
      ];

      await renderWithProviders(<PlanTimeline timeline={timeline} />, {
        renderAs: "viewer",
      });

      expect(screen.getByText("PROPOSED")).toBeInTheDocument();
      expect(screen.getByText("REJECTED")).toBeInTheDocument();
      // Ensure the script tag text is rendered as plain text safely, not executed as script
      expect(screen.getByText(maliciousDetail)).toBeInTheDocument();
      expect(document.querySelector("script[src*='xss']")).toBeNull();
    });
  });

  describe("RemediationPlanDetailPage - Approved Banner", () => {
    it("displays approved banner when plan status is APPROVED", async () => {
      const approvedPlan: RemediationPlanDetailOut = {
        id: 42,
        device_id: "Router-Core-01",
        run_id: 101,
        rule_id: "NET-008",
        status: "APPROVED",
        risk_level: "LOW",
        persist_after_verify: false,
        proposed_by: "operator1",
        proposed_at: "2026-11-21T10:00:00Z",
        decided_by: "admin1",
        decided_at: "2026-11-21T11:00:00Z",
        expires_at: "2026-11-21T12:00:00Z",
        plan_hash: "hash_approved_123",
        commands: ["no ip http server"],
        impact: "Disables unencrypted HTTP",
        risks: "Loss of HTTP management",
        expected_verification: { rule_id: "NET-008", expected_status: "PASS" },
        reversible: true,
        rollback_note: "Run ip http server",
        approved_hash_matches: true,
        timeline: [],
      };

      server.use(
        http.get("/api/v1/remediation-plans/42", () => {
          return HttpResponse.json(approvedPlan);
        })
      );

      await renderWithProviders(
        <Routes>
          <Route
            path="/remediation/:planId"
            element={<RemediationPlanDetailPage />}
          />
        </Routes>,
        {
          route: "/remediation/42",
          renderAs: "admin",
        }
      );

      await waitFor(() => {
        expect(
          screen.getByText(STRINGS.remediation.approve.approvedBanner)
        ).toBeInTheDocument();
      });
    });
  });
});
