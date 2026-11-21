import React from "react";
import { useQuery } from "@tanstack/react-query";
import { GitCompare, AlertTriangle, CheckCircle, Clock, HelpCircle } from "lucide-react";
import { CompareOut, FindingChangeOut } from "../../types/api";
import { compareAuditRuns } from "../../services/auditsApi";
import { Spinner } from "../ui/Spinner";
import { ErrorBanner } from "../ui/ErrorBanner";
import { SeverityBadge } from "./SeverityBadge";
import { StatusBadge } from "./StatusBadge";
import { STRINGS } from "../../i18n/strings";

interface ComparePanelProps {
  runId: number;
}

export function ComparePanel({ runId }: ComparePanelProps): React.JSX.Element {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<CompareOut, Error>({
    queryKey: ["audit-compare", runId],
    queryFn: () => compareAuditRuns(runId),
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs flex items-center justify-center space-x-2 text-gray-500 text-sm">
        <Spinner size="sm" className="text-indigo-600" />
        <span>Đang so sánh với lần kiểm toán trước...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorBanner
        title="Lỗi so sánh kết quả"
        message={error?.message || "Không thể so sánh kết quả kiểm toán."}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!data || !data.has_previous) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs text-center text-sm text-gray-500">
        <div className="flex justify-center mb-2">
          <GitCompare className="w-6 h-6 text-gray-400" />
        </div>
        <p className="font-medium text-gray-700">{STRINGS.compare.title}</p>
        <p className="text-xs text-gray-400 mt-1">{STRINGS.compare.noPrevious}</p>
      </div>
    );
  }

  const regressions = data.changes.filter((d: FindingChangeOut) => d.kind === "REGRESSION");
  const fixed = data.changes.filter((d: FindingChangeOut) => d.kind === "FIXED");
  const persisting = data.changes.filter((d: FindingChangeOut) => d.kind === "PERSISTING");
  const others = data.changes.filter(
    (d: FindingChangeOut) => d.kind !== "REGRESSION" && d.kind !== "FIXED" && d.kind !== "PERSISTING"
  );

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-gray-100 pb-4 gap-2">
        <div className="flex items-center space-x-2">
          <GitCompare className="w-5 h-5 text-indigo-600" />
          <h2 className="text-base font-semibold text-gray-900">{STRINGS.compare.title}</h2>
          <span className="text-xs text-gray-500 font-mono">
            (Audit #{data.to_run_id} vs #{data.from_run_id})
          </span>
        </div>
        <div className="flex items-center space-x-3 text-xs">
          <span className="px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 font-medium border border-rose-200">
            {STRINGS.compare.regression}: {regressions.length}
          </span>
          <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium border border-emerald-200">
            {STRINGS.compare.fixed}: {fixed.length}
          </span>
          <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 font-medium border border-amber-200">
            {STRINGS.compare.persisting}: {persisting.length}
          </span>
        </div>
      </div>

      {regressions.length > 0 && (
        <DiffSection
          title={STRINGS.compare.regression}
          items={regressions}
          icon={<AlertTriangle className="w-4 h-4 text-rose-600" />}
          badgeColor="bg-rose-50 text-rose-700 border-rose-200"
        />
      )}

      {fixed.length > 0 && (
        <DiffSection
          title={STRINGS.compare.fixed}
          items={fixed}
          icon={<CheckCircle className="w-4 h-4 text-emerald-600" />}
          badgeColor="bg-emerald-50 text-emerald-700 border-emerald-200"
        />
      )}

      {persisting.length > 0 && (
        <DiffSection
          title={STRINGS.compare.persisting}
          items={persisting}
          icon={<Clock className="w-4 h-4 text-amber-600" />}
          badgeColor="bg-amber-50 text-amber-700 border-amber-200"
        />
      )}

      {others.length > 0 && (
        <DiffSection
          title={STRINGS.compare.other}
          items={others}
          icon={<HelpCircle className="w-4 h-4 text-gray-500" />}
          badgeColor="bg-gray-50 text-gray-700 border-gray-200"
        />
      )}

      {data.changes.length === 0 && (
        <p className="text-center text-xs text-gray-500 py-4">Không có khác biệt nào.</p>
      )}
    </div>
  );
}

interface DiffSectionProps {
  title: string;
  items: FindingChangeOut[];
  icon: React.ReactNode;
  badgeColor: string;
}

function DiffSection({ title, items, icon, badgeColor }: DiffSectionProps): React.JSX.Element {
  return (
    <div className="space-y-2">
      <div className="flex items-center space-x-2">
        {icon}
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">{title}</h3>
        <span className={`text-[10px] px-1.5 py-0.2 rounded-full border font-semibold ${badgeColor}`}>
          {items.length}
        </span>
      </div>
      <div className="overflow-x-auto border border-gray-100 rounded-lg">
        <table className="min-w-full divide-y divide-gray-100 text-left text-xs">
          <thead className="bg-gray-50/75 text-gray-500">
            <tr>
              <th className="py-2 px-3 font-semibold w-28">{STRINGS.compare.colRule}</th>
              <th className="py-2 px-3 font-semibold">{STRINGS.compare.colTitle}</th>
              <th className="py-2 px-3 font-semibold w-24 text-center">{STRINGS.compare.colBefore}</th>
              <th className="py-2 px-3 font-semibold w-24 text-center">{STRINGS.compare.colAfter}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {items.map((item) => (
              <tr key={item.rule_id} className="hover:bg-gray-50/50">
                <td className="py-2.5 px-3 font-mono font-medium text-gray-900">
                  <div className="flex items-center space-x-1.5">
                    <span>{item.rule_id}</span>
                    {(item.after_severity || item.before_severity) && (
                      <SeverityBadge
                        severity={
                          (item.after_severity || item.before_severity) as
                            | "CRITICAL"
                            | "HIGH"
                            | "MEDIUM"
                            | "LOW"
                            | "INFO"
                        }
                      />
                    )}
                  </div>
                </td>
                <td className="py-2.5 px-3 text-gray-700 font-medium">{item.title}</td>
                <td className="py-2.5 px-3 text-center">
                  {item.before_status ? (
                    <StatusBadge
                      status={item.before_status as "PASS" | "FAIL" | "UNKNOWN"}
                    />
                  ) : (
                    <span className="text-gray-400 font-mono text-[11px]">-</span>
                  )}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {item.after_status ? (
                    <StatusBadge
                      status={item.after_status as "PASS" | "FAIL" | "UNKNOWN"}
                    />
                  ) : (
                    <span className="text-gray-400 font-mono text-[11px]">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
