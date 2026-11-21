import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getRemediationPlan,
  cancelRemediationPlan,
  getExecutionStatus,
  listPlanExecutions,
} from "../services/remediationApi";
import { PlanStatusBadge } from "../components/remediation/PlanStatusBadge";
import { PlanTimeline } from "../components/remediation/PlanTimeline";
import { ApproveDialog } from "../components/remediation/ApproveDialog";
import { RejectDialog } from "../components/remediation/RejectDialog";
import { ApplyDialog } from "../components/remediation/ApplyDialog";
import { ExecutionProgress } from "../components/remediation/ExecutionProgress";
import { ExecutionResultBanner } from "../components/remediation/ExecutionResultBanner";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { useAuth } from "../auth/AuthProvider";
import { STRINGS } from "../i18n/strings";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Ban,
  Terminal,
  Shield,
  AlertTriangle,
  RotateCcw,
  Hash,
  Info,
  Play,
  ShieldAlert,
} from "lucide-react";

export function RemediationPlanDetailPage(): React.JSX.Element {
  const { planId } = useParams<{ planId: string }>();
  const planIdNum = Number(planId);
  const isValidPlanId = !isNaN(planIdNum) && Number.isInteger(planIdNum) && planIdNum > 0;

  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [isRejectOpen, setIsRejectOpen] = useState(false);
  const [isApplyOpen, setIsApplyOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: plan,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["remediation-plan-detail", planIdNum],
    queryFn: () => getRemediationPlan(planIdNum),
    enabled: isValidPlanId,
  });

  const { data: execStatus } = useQuery({
    queryKey: ["remediation-exec-status"],
    queryFn: () => getExecutionStatus(),
  });

  const {
    data: executions,
    refetch: refetchExecutions,
  } = useQuery({
    queryKey: ["remediation-executions", planIdNum],
    queryFn: () => listPlanExecutions(planIdNum),
    enabled: isValidPlanId,
    refetchInterval: (query) => {
      const data = query.state.data;
      const latest = data && data.length > 0 ? data[0] : null;
      return latest?.result === "RUNNING" ? 2000 : false;
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelRemediationPlan(planIdNum),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["remediation-plan-detail", planIdNum] });
      queryClient.invalidateQueries({ queryKey: ["device-remediation-plans"] });
    },
    onError: (err: Error) => {
      setActionError(err.message || "Không thể hủy kế hoạch.");
    },
  });

  if (!isValidPlanId) {
    return (
      <div className="py-12 text-center">
        <p className="text-gray-500">Mã kế hoạch không hợp lệ.</p>
        <Link to="/remediation" className="text-sky-600 hover:underline mt-2 inline-block">
          Quay lại danh sách kế hoạch
        </Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <Spinner size="lg" className="text-sky-600" />
        <p className="text-sm text-gray-500">Đang tải chi tiết kế hoạch #{planId}...</p>
      </div>
    );
  }

  if (isError || !plan) {
    return (
      <div className="space-y-4">
        <Link
          to="/remediation"
          className="inline-flex items-center gap-1.5 text-xs text-sky-600 hover:text-sky-800 font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Quay lại danh sách kế hoạch</span>
        </Link>
        <ErrorBanner
          title="Không tìm thấy kế hoạch khắc phục"
          message={error instanceof Error ? error.message : "Kế hoạch không tồn tại."}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const isAdmin = user?.role === "admin";
  const isProposer = user?.username === plan.proposed_by;
  const canCancel =
    (plan.status === "PROPOSED" || plan.status === "APPROVED") &&
    (isAdmin || isProposer);
  const canApprove = plan.status === "PROPOSED" && isAdmin;
  const canReject = plan.status === "PROPOSED" && isAdmin;
  const canApply =
    plan.status === "APPROVED" &&
    isAdmin &&
    execStatus &&
    execStatus.mode !== "off";

  const latestExecution = executions && executions.length > 0 ? executions[0] : null;

  const riskVariant =
    plan.risk_level === "HIGH"
      ? "danger"
      : plan.risk_level === "MEDIUM"
      ? "warning"
      : "info";

  const handleCancelClick = () => {
    if (window.confirm(STRINGS.remediation.cancel.confirm)) {
      setActionError(null);
      cancelMutation.mutate();
    }
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center space-x-2 text-xs text-gray-500">
        <Link to="/remediation" className="hover:text-gray-900 font-medium transition-colors">
          {STRINGS.remediation.nav}
        </Link>
        <span>/</span>
        <Link
          to={`/devices/${encodeURIComponent(plan.device_id)}`}
          className="hover:text-gray-900 font-medium transition-colors"
        >
          {plan.device_id}
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-semibold">Kế hoạch #{plan.id}</span>
      </div>

      {actionError && (
        <ErrorBanner message={actionError} />
      )}

      {/* Mode off banner when APPROVED */}
      {plan.status === "APPROVED" && (!execStatus || execStatus.mode === "off") && (
        <div className="rounded-xl bg-emerald-50 p-4 border border-emerald-200 flex items-start space-x-3">
          <Info className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-emerald-900">Kế hoạch đã được duyệt</h4>
            <p className="mt-0.5 text-xs text-emerald-700">
              {STRINGS.remediation.approve.approvedBanner}
            </p>
          </div>
        </div>
      )}

      {/* Execution Result Banner */}
      {latestExecution && (
        <ExecutionResultBanner execution={latestExecution} />
      )}

      {/* Execution Progress Stepper */}
      {latestExecution && (
        <ExecutionProgress
          execution={latestExecution}
          onRefresh={() => {
            refetch();
            refetchExecutions();
          }}
        />
      )}

      {/* Header Card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                Kế hoạch #{plan.id} - {plan.rule_id}
              </h1>
              <PlanStatusBadge status={plan.status} />
              <Badge variant={riskVariant}>
                {STRINGS.remediation.riskLevels[plan.risk_level]}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              Thiết bị: <span className="font-mono font-medium text-gray-700">{plan.device_id}</span> | Lượt audit nguồn: #{plan.run_id} | Người đề xuất: <span className="font-medium text-gray-700">{plan.proposed_by}</span>
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center space-x-2">
            {canApprove && (
              <Button
                variant="primary"
                icon={<CheckCircle2 className="w-4 h-4" />}
                onClick={() => setIsApproveOpen(true)}
              >
                {STRINGS.remediation.approve.btnApprove}
              </Button>
            )}
            {canReject && (
              <Button
                variant="danger"
                icon={<XCircle className="w-4 h-4" />}
                onClick={() => setIsRejectOpen(true)}
              >
                {STRINGS.remediation.reject.btnReject}
              </Button>
            )}
            {canApply && (
              <Button
                variant={execStatus?.mode === "dry_run" ? "secondary" : "danger"}
                icon={
                  execStatus?.mode === "dry_run" ? (
                    <Play className="w-4 h-4" />
                  ) : (
                    <ShieldAlert className="w-4 h-4" />
                  )
                }
                onClick={() => setIsApplyOpen(true)}
              >
                {execStatus?.mode === "dry_run"
                  ? STRINGS.remediation.execute.btnDryRun
                  : STRINGS.remediation.execute.btnApply}
              </Button>
            )}
            {canCancel && (
              <Button
                variant="secondary"
                icon={<Ban className="w-4 h-4" />}
                onClick={handleCancelClick}
                disabled={cancelMutation.isPending}
              >
                {cancelMutation.isPending
                  ? STRINGS.remediation.cancel.cancelling
                  : STRINGS.remediation.cancel.btnCancel}
              </Button>
            )}
          </div>
        </div>

        {/* Quick meta grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-100 text-xs">
          <div>
            <span className="text-gray-400 block">Thời điểm đề xuất</span>
            <span className="font-medium text-gray-800">
              {new Date(plan.proposed_at).toLocaleString("vi-VN")}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block">Hết hạn hiệu lực</span>
            <span className="font-medium text-gray-800">
              {new Date(plan.expires_at).toLocaleString("vi-VN")}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block">Ghi vào startup-config</span>
            <span className="font-medium text-gray-800">
              {plan.persist_after_verify ? "Có (write memory)" : "Không (chỉ running-config)"}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block">Người phê duyệt</span>
            <span className="font-medium text-gray-800">
              {plan.decided_by ? (
                `${plan.decided_by} (${new Date(plan.decided_at!).toLocaleDateString("vi-VN")})`
              ) : (
                "—"
              )}
            </span>
          </div>
        </div>

        {plan.decide_reason && (
          <div className="mt-4 p-3 bg-gray-50 border border-gray-100 rounded-lg text-xs">
            <span className="font-semibold text-gray-700 block mb-0.5">Lý do quyết định:</span>
            <p className="text-gray-600 whitespace-pre-wrap">{plan.decide_reason}</p>
          </div>
        )}
      </div>

      {/* Main Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Commands & Impacts */}
        <div className="lg:col-span-2 space-y-6">
          {/* Commands Block */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs space-y-3">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center space-x-1.5 uppercase tracking-wider text-xs">
              <Terminal className="w-4 h-4 text-sky-600" />
              <span>{STRINGS.remediation.preview.commandsTitle}</span>
            </h3>
            <pre className="p-4 bg-gray-900 text-emerald-400 font-mono text-xs rounded-lg overflow-x-auto border border-gray-800 whitespace-pre leading-relaxed">
              {plan.commands.join("\n")}
            </pre>
            <p className="text-[11px] text-gray-400">
              Các lệnh được lấy cố định từ mẫu an toàn đã kiểm chứng, không sử dụng trí tuệ nhân tạo (AI) để sinh lệnh trực tiếp.
            </p>
          </div>

          {/* Impact and Risks */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-sky-100 bg-sky-50/30 p-5 space-y-2">
              <h4 className="text-xs font-bold text-sky-800 uppercase tracking-wide flex items-center space-x-1.5">
                <Shield className="w-4 h-4 text-sky-600" />
                <span>{STRINGS.remediation.preview.impactTitle}</span>
              </h4>
              <p className="text-xs text-sky-950 leading-relaxed">{plan.impact}</p>
            </div>

            <div className="bg-white rounded-xl border border-amber-100 bg-amber-50/30 p-5 space-y-2">
              <h4 className="text-xs font-bold text-amber-800 uppercase tracking-wide flex items-center space-x-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>{STRINGS.remediation.preview.risksTitle}</span>
              </h4>
              <p className="text-xs text-amber-950 whitespace-pre-line leading-relaxed">
                {plan.risks}
              </p>
            </div>
          </div>

          {/* Verification & Rollback */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs space-y-4 text-xs">
            <div>
              <span className="font-semibold text-gray-800 block mb-1">
                {STRINGS.remediation.preview.verificationTitle}
              </span>
              <div className="font-mono bg-gray-50 border border-gray-200 rounded p-2 text-gray-800">
                {plan.expected_verification.rule_id} → {plan.expected_verification.expected_status}
              </div>
            </div>

            <div>
              <span className="font-semibold text-gray-800 block mb-1 flex items-center space-x-1">
                <RotateCcw className="w-3.5 h-3.5 text-gray-500" />
                <span>Khả năng hoàn tác:</span>
              </span>
              <p className="text-gray-600">{plan.rollback_note}</p>
            </div>

            <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-[11px] text-gray-400 font-mono">
              <span className="flex items-center space-x-1">
                <Hash className="w-3.5 h-3.5" />
                <span>Mã băm kế hoạch: {plan.plan_hash.slice(0, 16)}...</span>
              </span>
              {plan.approved_hash_matches && (
                <span className="text-emerald-600 font-medium">✓ Hash khớp với lúc duyệt</span>
              )}
            </div>
          </div>
        </div>

        {/* Right Col: Timeline */}
        <div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs space-y-4">
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider text-xs">
              {STRINGS.remediation.timeline.title}
            </h3>
            <PlanTimeline timeline={plan.timeline} />
          </div>
        </div>
      </div>

      {/* Dialogs */}
      {canApprove && (
        <ApproveDialog
          isOpen={isApproveOpen}
          onClose={() => setIsApproveOpen(false)}
          planId={plan.id}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["remediation-plan-detail", planIdNum] });
            queryClient.invalidateQueries({ queryKey: ["device-remediation-plans"] });
          }}
        />
      )}

      {canReject && (
        <RejectDialog
          isOpen={isRejectOpen}
          onClose={() => setIsRejectOpen(false)}
          planId={plan.id}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["remediation-plan-detail", planIdNum] });
            queryClient.invalidateQueries({ queryKey: ["device-remediation-plans"] });
          }}
        />
      )}

      {canApply && execStatus && (
        <ApplyDialog
          isOpen={isApplyOpen}
          onClose={() => setIsApplyOpen(false)}
          plan={plan}
          executionMode={execStatus.mode}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["remediation-plan-detail", planIdNum] });
            queryClient.invalidateQueries({ queryKey: ["remediation-executions", planIdNum] });
            queryClient.invalidateQueries({ queryKey: ["device-remediation-plans"] });
          }}
        />
      )}
    </div>
  );
}
