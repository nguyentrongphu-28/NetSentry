import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, ChevronRight, Copy, Check } from "lucide-react";
import { FindingOut } from "../../types/api";
import { StatusBadge } from "./StatusBadge";
import { SeverityBadge } from "./SeverityBadge";
import { STRINGS } from "../../i18n/strings";

export interface FindingRowProps {
  finding: FindingOut;
}

export function FindingRow({ finding }: FindingRowProps): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const copyTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
    };
  }, []);

  const handleCopyRemediation = async (e: React.MouseEvent): Promise<void> => {
    e.stopPropagation();
    setError(null);

    if (copyTimerRef.current !== null) {
      window.clearTimeout(copyTimerRef.current);
      copyTimerRef.current = null;
    }

    const clipboard: Clipboard | undefined = navigator.clipboard;
    if (!clipboard || typeof clipboard.writeText !== "function") {
      setCopied(false);
      setError(STRINGS.auditDetail.copyFailed);
      return;
    }

    try {
      await clipboard.writeText(finding.remediation);
      setCopied(true);
      copyTimerRef.current = window.setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch {
      setCopied(false);
      setError(STRINGS.auditDetail.copyFailed);
    }
  };

  return (
    <div className="border-b border-gray-100 last:border-b-0">
      {/* Header Row (Button for a11y keyboard and screen reader support) */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        aria-expanded={isExpanded}
        className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-gray-50 focus:outline-none focus:bg-gray-50 transition-colors"
      >
        <div className="flex items-center space-x-3 min-w-0 pr-4">
          <span className="text-gray-400 flex-shrink-0" aria-hidden="true">
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-600" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
          </span>
          <span className="font-mono text-xs font-semibold text-gray-900 flex-shrink-0">
            {finding.rule_id}
          </span>
          <span className="text-sm font-medium text-gray-700 truncate">
            {finding.title}
          </span>
        </div>

        <div className="flex items-center space-x-2 flex-shrink-0">
          <SeverityBadge severity={finding.severity} />
          <StatusBadge status={finding.status} />
        </div>
      </button>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="px-6 py-4 bg-gray-50/70 border-t border-gray-100 space-y-4 text-xs">
          {/* Rationale */}
          <div>
            <span className="font-semibold text-gray-900 block mb-1">
              {STRINGS.auditDetail.rationaleTitle}
            </span>
            <p className="text-gray-700 leading-relaxed">{finding.rationale}</p>
          </div>

          {/* Evidence */}
          <div>
            <span className="font-semibold text-gray-900 block mb-1">
              {STRINGS.auditDetail.evidenceTitle}
            </span>
            {finding.evidence && finding.evidence.length > 0 ? (
              <div>
                {finding.evidence.map((line, idx) => (
                  <pre
                    key={idx}
                    className="bg-gray-900 text-gray-100 p-3 rounded-lg font-mono text-xs overflow-x-auto whitespace-pre leading-relaxed shadow-inner mb-1"
                  >
                    {line}
                  </pre>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 italic">{STRINGS.auditDetail.noEvidence}</p>
            )}
          </div>

          {/* Remediation */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-gray-900">
                {STRINGS.auditDetail.remediationTitle}
              </span>
              <div className="flex items-center gap-2">
                {error && (
                  <span role="alert" className="text-xs text-red-600 font-medium">
                    {error}
                  </span>
                )}
                <button
                  type="button"
                  onClick={handleCopyRemediation}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-indigo-600 hover:text-indigo-800 bg-white hover:bg-indigo-50 border border-gray-200 shadow-xs transition-colors"
                >
                  {copied ? (
                    <span className="inline-flex items-center gap-1 text-emerald-700">
                      <Check className="w-3.5 h-3.5 text-emerald-600" aria-hidden="true" />
                      <span>{STRINGS.auditDetail.copied}</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1">
                      <Copy className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>{STRINGS.auditDetail.copyRemediation}</span>
                    </span>
                  )}
                </button>
                <span role="status" className="sr-only">
                  {copied ? STRINGS.auditDetail.copied : ""}
                </span>
              </div>
            </div>
            <pre className="bg-indigo-950 text-indigo-100 p-3 rounded-lg font-mono text-xs overflow-x-auto whitespace-pre leading-relaxed border border-indigo-900">
              {finding.remediation}
            </pre>
          </div>

          {/* Verification */}
          {finding.verification && (
            <div>
              <span className="font-semibold text-gray-900 block mb-1">
                {STRINGS.auditDetail.verificationTitle}
              </span>
              <pre className="bg-gray-800 text-gray-200 p-2.5 rounded font-mono text-xs overflow-x-auto whitespace-pre">
                {finding.verification}
              </pre>
            </div>
          )}

          {/* Disclaimer */}
          <div className="p-2.5 bg-amber-50/80 border border-amber-200/80 rounded text-amber-800 text-[11px] font-medium leading-normal">
            ℹ️ {STRINGS.auditDetail.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
}
