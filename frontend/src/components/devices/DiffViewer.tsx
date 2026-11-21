import React from "react";
import { AlertCircle } from "lucide-react";
import { ConfigDiffOut, DiffHunkOut, DiffLineOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";

interface DiffViewerProps {
  diff: ConfigDiffOut;
}

export function DiffViewer({ diff }: DiffViewerProps): React.JSX.Element {
  if (diff.identical) {
    return (
      <div className="p-6 text-center text-xs text-gray-500 bg-gray-50 rounded-lg border border-gray-200">
        {STRINGS.snapshots.identical}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {diff.truncated && (
        <div className="flex items-center space-x-2 p-2.5 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-800">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-amber-600" />
          <span>{STRINGS.snapshots.truncated}</span>
        </div>
      )}

      <div className="bg-slate-900 rounded-lg p-4 font-mono text-[11px] leading-5 overflow-x-auto text-slate-100 max-h-[500px]">
        {diff.hunks.map((hunk: DiffHunkOut, hIdx: number) => (
          <div key={hIdx} className="mb-3 last:mb-0">
            <div className="text-cyan-400 font-semibold mb-1">
              @@ -{hunk.old_start} +{hunk.new_start} @@
            </div>
            {hunk.lines.map((line: DiffLineOut, lIdx: number) => {
              let lineClass = "text-slate-400";
              if (line.op === "+") {
                lineClass = "text-emerald-400 bg-emerald-950/40 block -mx-4 px-4";
              } else if (line.op === "-") {
                lineClass = "text-rose-400 bg-rose-950/40 block -mx-4 px-4";
              }

              return (
                <div key={lIdx} className={lineClass}>
                  <span className="inline-block w-4 select-none opacity-70">{line.op}</span>
                  <span>{line.text || " "}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
