import React from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  ShieldAlert,
  GitCompare,
  Info,
} from "lucide-react";
import { RemediationExecutionOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";

interface ExecutionResultBannerProps {
  execution: RemediationExecutionOut;
}

export function ExecutionResultBanner({
  execution,
}: ExecutionResultBannerProps): React.JSX.Element | null {
  if (execution.result === "RUNNING") return null;

  return (
    <div className="space-y-3">
      {/* Needs Manual Attention Alert Callout */}
      {execution.needs_manual_attention && (
        <div className="p-4 bg-red-100 dark:bg-red-950/60 border-2 border-red-500 rounded-lg flex items-start gap-3 shadow-sm">
          <ShieldAlert className="w-6 h-6 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-red-900 dark:text-red-200 uppercase tracking-wide">
              {STRINGS.remediation.result.needsAttentionTitle}
            </h4>
            <p className="text-xs text-red-800 dark:text-red-300">
              {STRINGS.remediation.result.needsAttentionDesc}
            </p>
            {execution.failure_code && (
              <p className="text-xs font-mono font-semibold text-red-700 dark:text-red-400">
                Mã lỗi: {execution.failure_code}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Main Execution Result Banner */}
      {execution.result === "VERIFIED" && (
        <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 rounded-lg flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <p className="text-sm font-medium text-emerald-900 dark:text-emerald-200">
              {STRINGS.remediation.result.verified}
            </p>
          </div>
          {execution.post_run_id && (
            <Link
              to={
                execution.pre_run_id
                  ? `/audits/${execution.post_run_id}/compare?baseline=${execution.pre_run_id}`
                  : `/audits/${execution.post_run_id}`
              }
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shrink-0"
            >
              <GitCompare className="w-3.5 h-3.5" />
              {STRINGS.remediation.result.compareWithPostAudit}
            </Link>
          )}
        </div>
      )}

      {execution.result === "DRY_RUN_OK" && (
        <div className="p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-300 dark:border-blue-800 rounded-lg flex items-center gap-3">
          <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0" />
          <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
            {STRINGS.remediation.result.dryRunOk}
          </p>
        </div>
      )}

      {execution.result === "ROLLED_BACK" && (
        <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded-lg flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
            {STRINGS.remediation.result.rolledBack}
          </p>
        </div>
      )}

      {execution.result === "VERIFY_FAILED" && (
        <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded-lg flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
            {STRINGS.remediation.result.verifyFailed}
          </p>
        </div>
      )}

      {execution.result === "FAILED" && !execution.needs_manual_attention && (
        <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-300 dark:border-red-800 rounded-lg flex items-center gap-3">
          <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-900 dark:text-red-200">
              {STRINGS.remediation.result.failed}
            </p>
            {execution.failure_code && (
              <p className="text-xs text-red-700 dark:text-red-400 font-mono mt-0.5">
                Mã lỗi: {execution.failure_code}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
