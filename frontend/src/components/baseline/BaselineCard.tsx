import React from "react";
import { ShieldCheck, ShieldAlert, User, Calendar, FileText, Trash2 } from "lucide-react";
import { BaselineOut } from "../../types/api";
import { Button } from "../ui/Button";
import { formatDateTime } from "../../utils/format";
import { STRINGS } from "../../i18n/strings";
import { useCan } from "../../auth/useCan";

interface BaselineCardProps {
  baseline: BaselineOut | null;
  onRetire: () => void;
  isRetiring?: boolean;
}

export function BaselineCard({
  baseline,
  onRetire,
  isRetiring = false,
}: BaselineCardProps): React.JSX.Element {
  const canAdmin = useCan("device:delete"); // admin role check

  if (!baseline) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-xs text-gray-500 shadow-xs">
        <ShieldCheck className="w-8 h-8 text-gray-300 mx-auto mb-2" />
        <p className="font-medium text-gray-700">{STRINGS.baseline.cardTitle}</p>
        <p className="mt-1 text-gray-400">{STRINGS.baseline.noBaseline}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-indigo-100 p-6 shadow-xs space-y-4 relative overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-indigo-50 pb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 bg-indigo-50 text-indigo-700 rounded-lg">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">{STRINGS.baseline.cardTitle}</h2>
            <div className="flex items-center space-x-2 text-xs text-gray-500 mt-0.5">
              <span>Snapshot #{baseline.snapshot_id}</span>
              <span>•</span>
              <span className="font-mono text-[11px] text-gray-400">
                {baseline.content_sha256 ? baseline.content_sha256.substring(0, 10) + "..." : ""}
              </span>
            </div>
          </div>
        </div>

        {canAdmin && (
          <Button
            variant="secondary"
            size="sm"
            className="text-rose-600 hover:text-rose-800 hover:bg-rose-50 border-rose-200"
            icon={<Trash2 className="w-3.5 h-3.5" />}
            isLoading={isRetiring}
            onClick={onRetire}
          >
            {STRINGS.baseline.retireBtn}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-gray-400 flex items-center space-x-1">
            <User className="w-3.5 h-3.5" />
            <span>{STRINGS.baseline.approvedBy}</span>
          </span>
          <span className="font-semibold text-gray-800 mt-1 block">
            {baseline.approved_by}
          </span>
        </div>

        <div>
          <span className="text-gray-400 flex items-center space-x-1">
            <Calendar className="w-3.5 h-3.5" />
            <span>{STRINGS.baseline.approvedAt}</span>
          </span>
          <span className="text-gray-700 mt-1 block">
            {formatDateTime(baseline.approved_at)}
          </span>
        </div>

        <div>
          <span className="text-gray-400 flex items-center space-x-1">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>{STRINGS.baseline.failCount}</span>
          </span>
          <span
            className={`font-semibold mt-1 block ${
              baseline.fail_count_at_approval > 0 ? "text-rose-600" : "text-emerald-600"
            }`}
          >
            {baseline.fail_count_at_approval}
          </span>
        </div>

        <div>
          <span className="text-gray-400 flex items-center space-x-1">
            <FileText className="w-3.5 h-3.5" />
            <span>{STRINGS.baseline.note}</span>
          </span>
          <span className="text-gray-700 mt-1 block truncate select-text" title={baseline.note || ""}>
            {baseline.note || "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
