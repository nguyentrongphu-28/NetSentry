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
import { ApplyDialog } from "../components/remediation/ApplyDialog";
import { ExecutionProgress } from "../components/remediation/ExecutionProgress";
import { ExecutionResultBanner } from "../components/remediation/ExecutionResultBanner";
import { ManualAttentionList } from "../components/remediation/ManualAttentionList";
import { PlanTimeline } from "../components/remediation/PlanTimeline";
import { RemediationPlanDetailPage } from "../pages/RemediationPlanDetailPage";
import {
  AttentionPlanOut,
  FindingOut,
  ManualGuidanceOut,
  PlanEventOut,
  RemediationExecutionOut,
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

  describe("Remediation Execution Flow (ApplyDialog, Progress, Results & Attention)", () => {
    const mockPlanForApply: RemediationPlanDetailOut = {
      id: 55,
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
      plan_hash: "hash_approved_55",
      commands: ["no ip http server"],
      rollback_commands: ["ip http server"],
      impact: "Disables HTTP",
      risks: "Loss of HTTP management",
      expected_verification: { rule_id: "NET-008", expected_status: "PASS" },
      reversible: true,
      rollback_note: "Run ip http server",
      approved_hash_matches: true,
      timeline: [],
    };

    it("ApplyDialog enforces device confirmation match, password, and checkbox", async () => {
      const onSuccess = vi.fn();
      const onClose = vi.fn();
      let capturedBody: unknown = null;

      server.use(
        http.post("/api/v1/remediation-plans/55/apply", async ({ request }) => {
          capturedBody = await request.json();
          return HttpResponse.json(
            { plan_id: 55, execution_id: 99, mode: "live" },
            { status: 202 }
          );
        })
      );

      const user = userEvent.setup();
      await renderWithProviders(
        <ApplyDialog
          isOpen={true}
          onClose={onClose}
          plan={mockPlanForApply}
          executionMode="live"
          onSuccess={onSuccess}
        />,
        { renderAs: "admin" }
      );

      const submitBtn = screen.getByRole("button", {
        name: new RegExp(STRINGS.remediation.execute.btnSubmitApply, "i"),
      });
      expect(submitBtn).toBeDisabled();

      // Enter wrong device ID
      const deviceInput = screen.getByLabelText(/xác nhận tên thiết bị/i);
      await user.type(deviceInput, "Wrong-Device");
      expect(submitBtn).toBeDisabled();
      expect(
        screen.getByText(STRINGS.remediation.execute.confirmDeviceMismatch)
      ).toBeInTheDocument();

      // Fix device ID
      await user.clear(deviceInput);
      await user.type(deviceInput, "Router-Core-01");
      expect(submitBtn).toBeDisabled();

      // Enter password
      const passInput = screen.getByLabelText(/mật khẩu quản trị/i);
      await user.type(passInput, "SecretAdmin123!");
      expect(submitBtn).toBeDisabled();

      // Check confirm checkbox
      const checkbox = screen.getByRole("checkbox");
      await user.click(checkbox);
      expect(submitBtn).toBeEnabled();

      // Submit
      await user.click(submitBtn);

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(99, "live");
      });

      expect(capturedBody).toEqual({
        confirm_device_id: "Router-Core-01",
        password: "SecretAdmin123!",
      });
    });

    it("ExecutionProgress renders steps and statuses correctly", async () => {
      const mockExecution: RemediationExecutionOut = {
        id: 99,
        plan_id: 55,
        mode: "live",
        started_at: "2026-11-21T11:05:00Z",
        finished_at: "2026-11-21T11:06:00Z",
        started_by: "admin1",
        result: "VERIFIED",
        failure_code: null,
        changes_sent: true,
        pre_run_id: 101,
        post_run_id: 102,
        rollback_run_id: null,
        persist_status: "NOT_REQUESTED",
        needs_manual_attention: false,
        steps: [
          {
            step: "pre_check_audit",
            status: "SUCCESS",
            at: "2026-11-21T11:05:05Z",
            detail: "Pre-check audit #101 passed",
          },
          {
            step: "write_config",
            status: "SUCCESS",
            at: "2026-11-21T11:05:20Z",
            detail: "1 command sent",
          },
          {
            step: "post_audit",
            status: "SUCCESS",
            at: "2026-11-21T11:05:55Z",
            detail: "Audit #102: PASS",
          },
        ],
      };

      await renderWithProviders(
        <ExecutionProgress execution={mockExecution} />,
        { renderAs: "admin" }
      );

      expect(screen.getByText(/tiến trình thực thi/i)).toBeInTheDocument();
      expect(
        screen.getByText(STRINGS.remediation.progress.stepPrecheck)
      ).toBeInTheDocument();
      expect(
        screen.getByText(STRINGS.remediation.progress.stepWrite)
      ).toBeInTheDocument();
      expect(
        screen.getByText(STRINGS.remediation.progress.stepPostAudit)
      ).toBeInTheDocument();
      expect(screen.getByText("Pre-check audit #101 passed")).toBeInTheDocument();
    });

    it("ExecutionResultBanner renders VERIFIED with compare link and critical attention banner", async () => {
      const verifiedExec: RemediationExecutionOut = {
        id: 99,
        plan_id: 55,
        mode: "live",
        started_at: "2026-11-21T11:05:00Z",
        finished_at: "2026-11-21T11:06:00Z",
        started_by: "admin1",
        result: "VERIFIED",
        failure_code: null,
        changes_sent: true,
        pre_run_id: 101,
        post_run_id: 102,
        rollback_run_id: null,
        persist_status: "NOT_REQUESTED",
        needs_manual_attention: false,
        steps: [],
      };

      const { unmount } = await renderWithProviders(
        <ExecutionResultBanner execution={verifiedExec} />,
        { renderAs: "admin" }
      );

      expect(
        screen.getByText(STRINGS.remediation.result.verified)
      ).toBeInTheDocument();
      expect(
        screen.getByText(STRINGS.remediation.result.compareWithPostAudit)
      ).toBeInTheDocument();

      unmount();

      // Now test critical attention alert
      const attentionExec: RemediationExecutionOut = {
        ...verifiedExec,
        result: "FAILED",
        failure_code: "POST_AUDIT_STILL_FAILING",
        needs_manual_attention: true,
      };

      await renderWithProviders(
        <ExecutionResultBanner execution={attentionExec} />,
        { renderAs: "admin" }
      );

      expect(
        screen.getByText(STRINGS.remediation.result.needsAttentionTitle)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/POST_AUDIT_STILL_FAILING/)
      ).toBeInTheDocument();
    });

    it("ManualAttentionList displays attention items and allows Admin acknowledge", async () => {
      const mockAttention: AttentionPlanOut[] = [
        {
          execution_id: 99,
          plan_id: 55,
          device_id: "Router-Core-01",
          rule_id: "NET-008",
          started_at: "2026-11-21T11:05:00Z",
          finished_at: "2026-11-21T11:06:00Z",
          failure_code: "WRITE_FAILED",
          changes_sent: true,
          acknowledged_at: null,
          acknowledged_by: null,
          acknowledgement_note: null,
        },
      ];

      const onRefresh = vi.fn();
      let capturedAckBody: unknown = null;

      server.use(
        http.post(
          "/api/v1/remediation/executions/99/acknowledge",
          async ({ request }) => {
            capturedAckBody = await request.json();
            return new HttpResponse(null, { status: 204 });
          }
        )
      );

      const user = userEvent.setup();
      await renderWithProviders(
        <ManualAttentionList
          attentionList={mockAttention}
          onRefresh={onRefresh}
        />,
        { renderAs: "admin" }
      );

      expect(
        screen.getByText(STRINGS.remediation.attention.title)
      ).toBeInTheDocument();
      expect(screen.getByText("Router-Core-01")).toBeInTheDocument();

      const ackBtn = screen.getByRole("button", {
        name: new RegExp(STRINGS.remediation.attention.ackBtn, "i"),
      });
      await user.click(ackBtn);

      expect(
        screen.getByText(STRINGS.remediation.attention.ackDialogTitle)
      ).toBeInTheDocument();

      const noteTextarea = screen.getByPlaceholderText(
        STRINGS.remediation.attention.ackNotePlaceholder
      );
      await user.type(noteTextarea, "Checked device directly via console; rolled back safely.");

      const confirmBtn = screen.getByRole("button", {
        name: new RegExp(STRINGS.remediation.attention.ackConfirm, "i"),
      });
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(onRefresh).toHaveBeenCalled();
      });

      expect(capturedAckBody).toEqual({
        note: "Checked device directly via console; rolled back safely.",
      });
    });
  });
});
