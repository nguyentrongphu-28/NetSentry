import React from "react";
import { CheckCircle2, AlertOctagon, ShieldAlert, ArrowRight } from "lucide-react";
import { DriftReportOut, BlockChangeOut } from "../../types/api";
import { Button } from "../ui/Button";
import { STRINGS } from "../../i18n/strings";
import { useCan } from "../../auth/useCan";

interface DriftSummaryProps {
  report: DriftReportOut | null;
  onViewDetail?: () => void;
  isLoadingDetail?: boolean;
}

export function DriftSummary({
  report,
  onViewDetail,
  isLoadingDetail = false,
}: DriftSummaryProps): React.JSX.Element {
  const canOperator = useCan("audit:run"); // operator or admin

  if (!report) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-xs text-gray-400 shadow-xs">
        Chưa có dữ liệu phân tích lệch chuẩn (Drift).
      </div>
    );
  }

  const { summary, blocks } = report;
  const isSync = summary.status === "IN_SYNC";

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-gray-100 pb-4">
        <div className="flex items-center space-x-2">
          {isSync ? (
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          ) : (
            <div className="p-2 bg-amber-50 text-amber-600 rounded-lg">
              <AlertOctagon className="w-5 h-5" />
            </div>
          )}
          <div>
            <h2 className="text-sm font-semibold text-gray-900">{STRINGS.drift.title}</h2>
            <p className="text-xs text-gray-500">
              {isSync ? STRINGS.drift.inSync : STRINGS.drift.drifted}
            </p>
          </div>
        </div>

        {canOperator && !isSync && onViewDetail && (
          <Button
            variant="secondary"
            size="sm"
            icon={<ArrowRight className="w-3.5 h-3.5" />}
            isLoading={isLoadingDetail}
            onClick={onViewDetail}
          >
            {STRINGS.drift.viewDetailBtn}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
        <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg">
          <span className="text-gray-500 block">{STRINGS.drift.addedBlocks}</span>
          <span className="text-lg font-bold text-gray-900 font-mono mt-0.5 block">
            {summary.added_blocks}
          </span>
        </div>

        <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg">
          <span className="text-gray-500 block">{STRINGS.drift.removedBlocks}</span>
          <span className="text-lg font-bold text-gray-900 font-mono mt-0.5 block">
            {summary.removed_blocks}
          </span>
        </div>

        <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg">
          <span className="text-gray-500 block">{STRINGS.drift.changedBlocks}</span>
          <span className="text-lg font-bold text-gray-900 font-mono mt-0.5 block">
            {summary.changed_blocks}
          </span>
        </div>

        <div className="p-3 bg-rose-50/60 border border-rose-100 rounded-lg">
          <span className="text-rose-700 block flex items-center space-x-1 font-medium">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
            <span>{STRINGS.drift.securityRelevant}</span>
          </span>
          <span className="text-lg font-bold text-rose-700 font-mono mt-0.5 block">
            {summary.security_relevant_count}
          </span>
        </div>
      </div>

      {!isSync && blocks.length > 0 && (
        <div className="space-y-2 pt-2">
          <h3 className="text-xs font-semibold text-gray-700">Các khối thay đổi:</h3>
          <div className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
            {blocks.slice(0, 10).map((b: BlockChangeOut, idx: number) => (
              <div
                key={idx}
                className={`p-2.5 flex items-center justify-between text-xs ${
                  b.security_relevant ? "bg-amber-50/40" : "bg-white"
                }`}
              >
                <div className="flex items-center space-x-2 font-mono">
                  <span
                    className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                      b.kind === "ADDED"
                        ? "bg-emerald-100 text-emerald-800"
                        : b.kind === "REMOVED"
                        ? "bg-rose-100 text-rose-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {b.kind}
                  </span>
                  <span className="font-semibold text-gray-900">{b.key}</span>
                </div>
                <div className="flex items-center space-x-3 text-gray-500 font-mono text-[11px]">
                  {b.added_count > 0 && (
                    <span className="text-emerald-600">+{b.added_count}</span>
                  )}
                  {b.removed_count > 0 && (
                    <span className="text-rose-600">-{b.removed_count}</span>
                  )}
                  {b.security_relevant && (
                    <span className="text-rose-600 font-sans text-[10px] bg-rose-50 px-1 py-0.2 rounded border border-rose-200 font-medium">
                      Bảo mật
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
