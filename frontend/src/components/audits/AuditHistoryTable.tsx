import React from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { AuditRunSummaryOut } from "../../types/api";
import { StatusBadge } from "./StatusBadge";
import { formatDateTime } from "../../utils/format";
import { STRINGS } from "../../i18n/strings";
import { Button } from "../ui/Button";

export interface AuditHistoryTableProps {
  audits: AuditRunSummaryOut[];
  total: number;
  limit: number;
  offset: number;
  onPageChange: (newOffset: number) => void;
  isLoading?: boolean;
}

export function AuditHistoryTable({
  audits,
  total,
  limit,
  offset,
  onPageChange,
  isLoading = false,
}: AuditHistoryTableProps): React.JSX.Element {
  const fromIndex = total === 0 ? 0 : offset + 1;
  const toIndex = Math.min(offset + limit, total);

  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  if (audits.length === 0 && !isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-sm text-gray-500">
        {STRINGS.deviceDetail.emptyHistory}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
          <thead className="bg-gray-50/75 text-gray-600 font-semibold uppercase tracking-wider">
            <tr>
              <th scope="col" className="px-6 py-3">Lượt audit</th>
              <th scope="col" className="px-6 py-3">Thời gian</th>
              <th scope="col" className="px-6 py-3">Trạng thái</th>
              <th scope="col" className="px-6 py-3">Kết quả</th>
              <th scope="col" className="px-6 py-3 text-right">Chi tiết</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {audits.map((run) => (
              <tr key={run.id} className="hover:bg-gray-50/60 transition-colors">
                <td className="px-6 py-3.5 font-mono font-medium text-gray-900">
                  #{run.id}
                </td>
                <td className="px-6 py-3.5 text-gray-600 whitespace-nowrap">
                  {formatDateTime(run.started_at)}
                </td>
                <td className="px-6 py-3.5 whitespace-nowrap">
                  <StatusBadge status={run.status} />
                </td>
                <td className="px-6 py-3.5 whitespace-nowrap">
                  <div className="flex items-center space-x-1.5 font-mono text-[11px]">
                    <span className="text-emerald-700 font-bold">{run.pass_count}P</span>
                    <span className="text-gray-300">/</span>
                    <span className="text-rose-700 font-bold">{run.fail_count}F</span>
                    <span className="text-gray-300">/</span>
                    <span className="text-amber-700 font-bold">{run.unknown_count}U</span>
                  </div>
                </td>
                <td className="px-6 py-3.5 text-right whitespace-nowrap">
                  <Link
                    to={`/audits/${run.id}`}
                    className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-900 font-medium hover:underline"
                  >
                    <span>Xem</span>
                    <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="px-6 py-3 bg-gray-50/50 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
        <div>
          <span>
            {STRINGS.deviceDetail.paginationShowing}{" "}
            <span className="font-semibold text-gray-800">
              {fromIndex}–{toIndex}
            </span>{" "}
            {STRINGS.deviceDetail.paginationOf}{" "}
            <span className="font-semibold text-gray-800">{total}</span>
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={!canPrev || isLoading}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            icon={<ChevronLeft className="w-3.5 h-3.5" />}
          >
            {STRINGS.deviceDetail.paginationPrev}
          </Button>

          <Button
            variant="secondary"
            size="sm"
            disabled={!canNext || isLoading}
            onClick={() => onPageChange(offset + limit)}
          >
            <span>{STRINGS.deviceDetail.paginationNext}</span>
            <ChevronRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}
