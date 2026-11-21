import React, { useEffect, useState } from "react";
import { Sparkles, AlertCircle, RefreshCw, ShieldAlert, AlertTriangle, Info } from "lucide-react";
import { AiExplanationOut, AiStatusOut, PriorityItemOut, RiskNoteOut } from "../../types/api";
import { getAiStatus, getAuditExplanation, generateAuditExplanation } from "../../services/auditsApi";
import { Button } from "../ui/Button";
import { Spinner } from "../ui/Spinner";
import { ErrorBanner } from "../ui/ErrorBanner";
import { STRINGS } from "../../i18n/strings";
import { useCan } from "../../auth/useCan";

interface AiExplainPanelProps {
  runId: number;
}

export function AiExplainPanel({ runId }: AiExplainPanelProps): React.JSX.Element | null {
  const canRun = useCan("audit:run");
  const [status, setStatus] = useState<AiStatusOut | null>(null);
  const [explanation, setExplanation] = useState<AiExplanationOut | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchStatusAndExisting = async (): Promise<void> => {
      setIsLoadingStatus(true);
      setError(null);
      try {
        const s = await getAiStatus();
        if (!isMounted) return;
        setStatus(s);

        if (s.enabled) {
          try {
            const exp = await getAuditExplanation(runId);
            if (isMounted) setExplanation(exp);
          } catch {
            // Not yet generated, ignore 404
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Không thể kiểm tra trạng thái AI");
        }
      } finally {
        if (isMounted) setIsLoadingStatus(false);
      }
    };

    void fetchStatusAndExisting();
    return () => {
      isMounted = false;
    };
  }, [runId]);

  const handleGenerate = async (force: boolean = false): Promise<void> => {
    setIsGenerating(true);
    setError(null);
    try {
      const res = await generateAuditExplanation(runId, force);
      setExplanation(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("AI_UNAVAILABLE") || msg.includes("503")) {
        setError(STRINGS.ai.unavailable);
      } else if (msg.includes("AI_BUSY") || msg.includes("429")) {
        setError(STRINGS.ai.busy);
      } else if (msg.includes("AI_OUTPUT_INVALID") || msg.includes("502")) {
        setError(STRINGS.ai.invalidOutput);
      } else {
        setError(msg || STRINGS.ai.unavailable);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  if (isLoadingStatus) {
    return null;
  }

  // If AI is completely disabled on server, do not render
  if (!status?.enabled) {
    return null;
  }

  return (
    <div className="bg-white rounded-xl border border-indigo-100 p-6 shadow-xs space-y-4 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-50 rounded-bl-full pointer-events-none -z-0 opacity-60" />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 relative z-10 border-b border-indigo-50 pb-4">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 bg-indigo-100 text-indigo-700 rounded-lg">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">{STRINGS.ai.title}</h2>
            <p className="text-xs text-gray-500">Mô hình: {status.model || "Local LLM"}</p>
          </div>
        </div>

        {canRun && (
          <div>
            {!explanation ? (
              <Button
                variant="primary"
                size="sm"
                icon={<Sparkles className="w-4 h-4" />}
                onClick={() => handleGenerate(false)}
                isLoading={isGenerating}
              >
                {STRINGS.ai.buttonExplain}
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                icon={<RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? "animate-spin" : ""}`} />}
                onClick={() => handleGenerate(true)}
                isLoading={isGenerating}
              >
                {STRINGS.ai.forceRegenerate}
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <ErrorBanner
          title="Lỗi phân tích AI"
          message={error}
          onRetry={() => handleGenerate(false)}
        />
      )}

      {/* Generating indicator */}
      {isGenerating && (
        <div className="py-8 flex flex-col items-center justify-center space-y-3 text-indigo-700">
          <Spinner size="md" className="text-indigo-600" />
          <p className="text-xs font-medium animate-pulse">{STRINGS.ai.generating}</p>
        </div>
      )}

      {/* Existing Explanation content */}
      {!isGenerating && explanation && (
        <div className="space-y-4 relative z-10 text-xs">
          {/* Summary */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-1.5">
            <h3 className="font-semibold text-slate-800 flex items-center space-x-1.5">
              <Info className="w-4 h-4 text-indigo-600" />
              <span>{STRINGS.ai.summaryTitle}</span>
            </h3>
            <p className="text-slate-700 leading-relaxed whitespace-pre-wrap select-text">
              {explanation.summary}
            </p>
          </div>

          {/* Priorities */}
          {explanation.priorities && explanation.priorities.length > 0 && (
            <div className="bg-amber-50/60 border border-amber-200 rounded-lg p-4 space-y-2">
              <h3 className="font-semibold text-amber-900 flex items-center space-x-1.5">
                <ShieldAlert className="w-4 h-4 text-amber-600" />
                <span>{STRINGS.ai.prioritiesTitle}</span>
              </h3>
              <ul className="list-disc list-inside space-y-1 text-amber-950 font-medium">
                {explanation.priorities.map((item: PriorityItemOut, idx: number) => (
                  <li key={idx} className="leading-relaxed select-text">
                    <span className="font-mono font-bold mr-1">{item.rule_id}:</span>
                    <span>{item.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Risks */}
          {explanation.risks && explanation.risks.length > 0 && (
            <div className="bg-rose-50/60 border border-rose-200 rounded-lg p-4 space-y-2">
              <h3 className="font-semibold text-rose-900 flex items-center space-x-1.5">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <span>{STRINGS.ai.risksTitle}</span>
              </h3>
              <ul className="list-disc list-inside space-y-1 text-rose-950">
                {explanation.risks.map((item: RiskNoteOut, idx: number) => (
                  <li key={idx} className="leading-relaxed select-text">
                    <span className="font-mono font-bold mr-1">{item.rule_id}:</span>
                    <span>{item.warning}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Disclaimer mandatory */}
          <div className="pt-2 border-t border-gray-100 flex items-center space-x-2 text-[11px] text-gray-500 italic">
            <AlertCircle className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
            <span>{STRINGS.ai.disclaimer}</span>
          </div>
        </div>
      )}
    </div>
  );
}
