import React from "react";
import { AlertTriangle, Clock, Server, Cpu } from "lucide-react";
import { AuditRunSummaryOut } from "../../types/api";
import { StatusBadge } from "./StatusBadge";
import { formatDateTime, formatDuration } from "../../utils/format";
import { STRINGS, getErrorCodeSuggestion } from "../../i18n/strings";

export interface AuditSummaryHeaderProps {
  summary: AuditRunSummaryOut;
}

export function AuditSummaryHeader({
  summary,
}: AuditSummaryHeaderProps): React.JSX.Element {
  const isFailed = summary.status === "FAILED";

  return (
    <div className="space-y-4">
      {/* Main Summary Card */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs p-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-5 border-b border-gray-100">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                Lượt kiểm toán #{summary.id}
              </h1>
              <StatusBadge status={summary.status} />
            </div>
            <p className="mt-1 text-xs text-gray-500">
              Kiểm toán thiết bị <span className="font-semibold text-gray-700">{summary.device_id}</span>
            </p>
          </div>

          {/* Counts overview */}
          <div className="flex items-center space-x-3">
            <div className="px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg text-center">
              <span className="block text-xs font-semibold text-emerald-800">
                {summary.pass_count}
              </span>
              <span className="text-[10px] text-emerald-600 font-medium">PASS</span>
            </div>
            <div className="px-3 py-1.5 bg-rose-50 border border-rose-200 rounded-lg text-center">
              <span className="block text-xs font-semibold text-rose-800">
                {summary.fail_count}
              </span>
              <span className="text-[10px] text-rose-600 font-medium">FAIL</span>
            </div>
            <div className="px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-lg text-center">
              <span className="block text-xs font-semibold text-amber-800">
                {summary.unknown_count}
              </span>
              <span className="text-[10px] text-amber-600 font-medium">UNKNOWN</span>
            </div>
          </div>
        </div>

        {/* Metadata Details Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-5 text-xs">
          <div className="flex items-start space-x-2">
            <Server className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="text-gray-500 block">{STRINGS.auditDetail.device}</span>
              <span className="font-semibold text-gray-900">{summary.device_id}</span>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <Cpu className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="text-gray-500 block">{STRINGS.auditDetail.hostname}</span>
              <span className="font-semibold text-gray-900">
                {summary.hostname || "Chưa xác định"}
              </span>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <Clock className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="text-gray-500 block">{STRINGS.auditDetail.startTime}</span>
              <span className="text-gray-900 font-medium">
                {formatDateTime(summary.started_at)}
              </span>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <Clock className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="text-gray-500 block">{STRINGS.auditDetail.duration}</span>
              <span className="text-gray-900 font-medium">
                {formatDuration(summary.started_at, summary.finished_at)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Prominent FAILED Alert Box */}
      {isFailed && (
        <div
          role="alert"
          className="p-5 bg-rose-50 border-2 border-rose-300 rounded-xl space-y-3 text-sm text-rose-950 shadow-xs"
        >
          <div className="flex items-center space-x-2 text-rose-800 font-bold text-base">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span>{STRINGS.auditDetail.failedAlertTitle}</span>
          </div>

          <div className="space-y-1.5 text-xs text-rose-900">
            {summary.error_code && (
              <p>
                <span className="font-semibold">{STRINGS.auditDetail.failedAlertCode}</span>{" "}
                <code className="bg-rose-100 text-rose-800 px-1.5 py-0.5 rounded font-mono font-bold">
                  {summary.error_code}
                </code>
              </p>
            )}
            {summary.error_message && (
              <p>
                <span className="font-semibold">Chi tiết:</span> {summary.error_message}
              </p>
            )}
            <div className="pt-2 border-t border-rose-200">
              <span className="font-semibold text-rose-950 block mb-0.5">
                {STRINGS.auditDetail.failedAlertSuggestion}
              </span>
              <p className="text-rose-800 leading-relaxed font-medium">
                👉 {getErrorCodeSuggestion(summary.error_code)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
