import React from "react";
import { DriftHistoryItemOut } from "../../types/api";
import { formatDateTime } from "../../utils/format";
import { STRINGS } from "../../i18n/strings";

interface DriftHistoryProps {
  history: DriftHistoryItemOut[];
}

export function DriftHistory({ history }: DriftHistoryProps): React.JSX.Element {
  if (history.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-xs text-gray-400">
        {STRINGS.drift.noHistory}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-900">{STRINGS.drift.historyTitle}</h3>
      <div className="overflow-x-auto border border-gray-200 rounded-xl bg-white shadow-xs">
        <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
          <thead className="bg-gray-50/75 text-gray-500 font-semibold">
            <tr>
              <th className="py-2.5 px-3">{STRINGS.drift.colRun}</th>
              <th className="py-2.5 px-3">{STRINGS.drift.colTime}</th>
              <th className="py-2.5 px-3">{STRINGS.drift.colStatus}</th>
              <th className="py-2.5 px-3">{STRINGS.drift.colAdded}</th>
              <th className="py-2.5 px-3">{STRINGS.drift.colRemoved}</th>
              <th className="py-2.5 px-3">{STRINGS.drift.colChanged}</th>
              <th className="py-2.5 px-3">{STRINGS.drift.colSec}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 font-normal">
            {history.map((it: DriftHistoryItemOut) => {
              const isSync = it.status === "IN_SYNC";
              return (
                <tr key={it.run_id} className="hover:bg-gray-50/60">
                  <td className="py-2.5 px-3 font-medium text-gray-900 font-mono">
                    #{it.run_id}
                  </td>
                  <td className="py-2.5 px-3 text-gray-600">
                    {formatDateTime(it.checked_at)}
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        isSync
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}
                    >
                      {it.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-gray-700 font-mono">+{it.added_blocks}</td>
                  <td className="py-2.5 px-3 text-gray-700 font-mono">-{it.removed_blocks}</td>
                  <td className="py-2.5 px-3 text-gray-700 font-mono">{it.changed_blocks}</td>
                  <td className="py-2.5 px-3">
                    {it.security_relevant_count > 0 ? (
                      <span className="text-rose-600 font-bold font-mono">
                        {it.security_relevant_count}
                      </span>
                    ) : (
                      <span className="text-gray-400 font-mono">0</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
