import React from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuditRun } from "../hooks/useAuditRun";
import { AuditSummaryHeader } from "../components/audits/AuditSummaryHeader";
import { FindingsTable } from "../components/audits/FindingsTable";
import { Spinner } from "../components/ui/Spinner";
import { ErrorBanner } from "../components/ui/ErrorBanner";

import { NotFoundPage } from "./NotFoundPage";
import { STRINGS } from "../i18n/strings";

export function AuditRunPage(): React.JSX.Element {
  const { runId } = useParams<{ runId: string }>();
  const runIdNum = Number(runId);
  const isValidRunId = !isNaN(runIdNum) && Number.isInteger(runIdNum) && runIdNum > 0;

  const {
    data: auditRun,
    isLoading,
    isError,
    error,
    refetch,
  } = useAuditRun(isValidRunId ? runIdNum : undefined);

  if (!isValidRunId) {
    return <NotFoundPage />;
  }

  if (isLoading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <Spinner size="lg" className="text-indigo-600" />
        <p className="text-sm text-gray-500">Đang tải kết quả kiểm toán #{runId}...</p>
      </div>
    );
  }

  if (isError || !auditRun) {
    return (
      <div className="space-y-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>{STRINGS.nav.backToDashboard}</span>
        </Link>
        <ErrorBanner
          title="Không tìm thấy lượt kiểm toán"
          message={error instanceof Error ? error.message : "Dữ liệu kiểm toán không tồn tại."}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const { summary, findings } = auditRun;
  const isFailed = summary.status === "FAILED";

  return (
    <div className="space-y-6">
      {/* Navigation Breadcrumb / Back Link */}
      <div className="flex items-center space-x-2 text-xs text-gray-500">
        <Link
          to="/"
          className="hover:text-gray-900 font-medium transition-colors"
        >
          {STRINGS.nav.dashboard}
        </Link>
        <span>/</span>
        <Link
          to={`/devices/${encodeURIComponent(summary.device_id)}`}
          className="hover:text-gray-900 font-medium transition-colors"
        >
          {summary.device_id}
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-semibold">Audit #{summary.id}</span>
      </div>

      {/* Summary Header Card + FAILED Alert if any */}
      <AuditSummaryHeader summary={summary} />

      {/* Findings Table only when status is COMPLETED */}
      {!isFailed && <FindingsTable findings={findings} />}
    </div>
  );
}
