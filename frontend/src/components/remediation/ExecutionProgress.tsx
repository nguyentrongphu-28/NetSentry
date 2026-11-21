import React, { useEffect } from "react";
import { CheckCircle2, XCircle, MinusCircle, Loader2 } from "lucide-react";
import { ExecutionStepOut, RemediationExecutionOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { formatDateTime } from "../../utils/format";

interface ExecutionProgressProps {
  execution: RemediationExecutionOut;
  onRefresh?: () => void;
}

const STEP_LABELS: Record<string, string> = {
  pre_check_audit: STRINGS.remediation.progress.stepPrecheck,
  write_config: STRINGS.remediation.progress.stepWrite,
  post_audit: STRINGS.remediation.progress.stepPostAudit,
  persist_config: STRINGS.remediation.progress.stepPersist,
  rollback: STRINGS.remediation.progress.stepRollback,
};

export function ExecutionProgress({
  execution,
  onRefresh,
}: ExecutionProgressProps): React.JSX.Element {
  // Polling while RUNNING
  useEffect(() => {
    if (execution.result !== "RUNNING" || !onRefresh) return;
    const interval = setInterval(() => {
      onRefresh();
    }, 2000);
    return () => clearInterval(interval);
  }, [execution.result, onRefresh]);

  const renderStatusIcon = (step: ExecutionStepOut) => {
    switch (step.status) {
      case "STARTED":
        return <Loader2 className="w-4 h-4 text-primary-500 animate-spin shrink-0" />;
      case "SUCCESS":
        return <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />;
      case "FAILED":
        return <XCircle className="w-4 h-4 text-red-500 shrink-0" />;
      case "SKIPPED":
        return <MinusCircle className="w-4 h-4 text-gray-400 shrink-0" />;
      default:
        return null;
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-gray-200 dark:border-gray-700">
        <h4 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          {execution.result === "RUNNING" && (
            <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />
          )}
          {STRINGS.remediation.progress.title}
          <span className="text-xs font-mono font-normal text-gray-500">
            #{execution.id} ({execution.mode})
          </span>
        </h4>
        <span className="text-xs text-gray-500">
          {formatDateTime(execution.started_at)}
        </span>
      </div>

      <div className="space-y-3">
        {execution.steps.map((step, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 text-sm p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
          >
            <div className="mt-0.5">{renderStatusIcon(step)}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-gray-800 dark:text-gray-200">
                  {STEP_LABELS[step.step] || step.step}
                </span>
                <span className="text-xs text-gray-400 shrink-0">
                  {formatDateTime(step.at)}
                </span>
              </div>
              {step.detail && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 break-words">
                  {step.detail}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
