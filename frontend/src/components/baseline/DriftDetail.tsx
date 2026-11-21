import React from "react";
import { AlertCircle, ShieldAlert } from "lucide-react";
import { DriftReportOut, BlockChangeOut } from "../../types/api";
import { Modal } from "../ui/Modal";
import { STRINGS } from "../../i18n/strings";

interface DriftDetailProps {
  isOpen: boolean;
  onClose: () => void;
  report: DriftReportOut | null;
}

export function DriftDetail({ isOpen, onClose, report }: DriftDetailProps): React.JSX.Element {
  if (!report) {
    return <></>;
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${STRINGS.drift.detailTitle}: Lượt Audit #${report.run_id}`}
      maxWidth="xl"
    >
      <div className="space-y-4 text-xs">
        {report.truncated && (
          <div className="p-2.5 bg-amber-50 border border-amber-200 text-amber-800 rounded flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>{STRINGS.drift.truncated}</span>
          </div>
        )}

        <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
          {report.blocks.map((block: BlockChangeOut, idx: number) => (
            <div
              key={idx}
              className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-xs"
            >
              {/* Header */}
              <div
                className={`p-2.5 flex items-center justify-between border-b ${
                  block.security_relevant
                    ? "bg-amber-50/70 border-amber-200"
                    : "bg-gray-50 border-gray-200"
                }`}
              >
                <div className="flex items-center space-x-2 font-mono">
                  <span
                    className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                      block.kind === "ADDED"
                        ? "bg-emerald-100 text-emerald-800"
                        : block.kind === "REMOVED"
                        ? "bg-rose-100 text-rose-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {block.kind}
                  </span>
                  <span className="font-bold text-gray-900">{block.key}</span>
                </div>
                {block.security_relevant && (
                  <div className="flex items-center space-x-1 text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200 font-sans text-[11px] font-medium">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    <span>{STRINGS.drift.securityRelevant}</span>
                  </div>
                )}
              </div>

              {/* Lines */}
              <div className="p-3 bg-slate-900 text-slate-100 font-mono text-[11px] leading-5 overflow-x-auto space-y-0.5">
                {block.removed_lines.map((l: string, lIdx: number) => (
                  <div key={`rem-${lIdx}`} className="text-rose-400 bg-rose-950/40 -mx-3 px-3">
                    <span className="select-none inline-block w-4">-</span>
                    <span>{l}</span>
                  </div>
                ))}
                {block.added_lines.map((l: string, lIdx: number) => (
                  <div key={`add-${lIdx}`} className="text-emerald-400 bg-emerald-950/40 -mx-3 px-3">
                    <span className="select-none inline-block w-4">+</span>
                    <span>{l}</span>
                  </div>
                ))}
                {block.added_lines.length === 0 && block.removed_lines.length === 0 && (
                  <div className="text-gray-400 italic">
                    (Không có nội dung dòng chi tiết hoặc ở chế độ công khai)
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Modal>
  );
}
