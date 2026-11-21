import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { ErrorBanner } from "../ui/ErrorBanner";
import { RemediationTemplateOut, isApiErrorResponse } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { proposeRemediationPlan } from "../../services/remediationApi";
import { ApiClientError } from "../../services/apiClient";
import { Shield, AlertTriangle, CheckCircle, Terminal } from "lucide-react";

interface RemediationPreviewDialogProps {
  isOpen: boolean;
  onClose: () => void;
  runId: number;
  template: RemediationTemplateOut | null;
}

export function RemediationPreviewDialog({
  isOpen,
  onClose,
  runId,
  template,
}: RemediationPreviewDialogProps): React.JSX.Element {
  const navigate = useNavigate();
  const [persistAfterVerify, setPersistAfterVerify] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!template) return <></>;

  const getErrorMessage = (err: unknown): string => {
    if (err instanceof ApiClientError) {
      const code = err.code as keyof typeof STRINGS.remediation.errors;
      return STRINGS.remediation.errors[code] || err.message;
    }
    if (isApiErrorResponse(err)) {
      const code = err.error.code as keyof typeof STRINGS.remediation.errors;
      return STRINGS.remediation.errors[code] || err.error.message;
    }
    if (err instanceof Error) {
      for (const [code, trans] of Object.entries(STRINGS.remediation.errors)) {
        if (err.message.includes(code)) return trans;
      }
      return err.message;
    }
    return "Đã xảy ra lỗi khi tạo kế hoạch khắc phục.";
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const createdPlan = await proposeRemediationPlan(runId, template.rule_id, {
        persist_after_verify: persistAfterVerify,
      });
      onClose();
      navigate(`/remediation/${createdPlan.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const riskBadgeVariant =
    template.risk_level === "HIGH"
      ? "danger"
      : template.risk_level === "MEDIUM"
      ? "warning"
      : "info";

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${STRINGS.remediation.preview.title} - ${template.rule_id}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorBanner message={error} />}

        {/* Risk Level and Title */}
        <div className="flex items-center justify-between">
          <h4 className="text-base font-semibold text-gray-900">{template.title}</h4>
          <div className="flex items-center space-x-2">
            <span className="text-xs text-gray-500">{STRINGS.remediation.preview.riskTitle}:</span>
            <Badge variant={riskBadgeVariant}>
              {STRINGS.remediation.riskLevels[template.risk_level]}
            </Badge>
          </div>
        </div>

        {/* Commands block (pure text in pre) */}
        <div>
          <span className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1 flex items-center space-x-1">
            <Terminal className="w-3.5 h-3.5" />
            <span>{STRINGS.remediation.preview.commandsTitle}</span>
          </span>
          <pre className="p-3 bg-gray-900 text-emerald-400 font-mono text-xs rounded-lg overflow-x-auto border border-gray-800 whitespace-pre">
            {template.commands.join("\n")}
          </pre>
        </div>

        {/* Impact */}
        <div className="rounded-lg bg-sky-50 p-3 border border-sky-200">
          <h5 className="text-xs font-bold text-sky-800 uppercase tracking-wide flex items-center space-x-1">
            <Shield className="w-3.5 h-3.5" />
            <span>{STRINGS.remediation.preview.impactTitle}</span>
          </h5>
          <p className="mt-1 text-sm text-sky-900">{template.impact}</p>
        </div>

        {/* Risks */}
        <div className="rounded-lg bg-amber-50 p-3 border border-amber-200">
          <h5 className="text-xs font-bold text-amber-800 uppercase tracking-wide flex items-center space-x-1">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{STRINGS.remediation.preview.risksTitle}</span>
          </h5>
          <p className="mt-1 text-sm text-amber-900 whitespace-pre-line">{template.risks}</p>
        </div>

        {/* Expected Verification */}
        <div className="rounded-lg bg-gray-50 p-3 border border-gray-200">
          <h5 className="text-xs font-bold text-gray-700 uppercase tracking-wide flex items-center space-x-1">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
            <span>{STRINGS.remediation.preview.verificationTitle}</span>
          </h5>
          <p className="mt-1 text-sm text-gray-800 font-mono">
            {template.rule_id} → PASS
          </p>
        </div>

        {/* Persist after verify checkbox */}
        <div className="pt-1 flex items-start space-x-3">
          <input
            id="persist-after-verify-checkbox"
            type="checkbox"
            checked={persistAfterVerify}
            onChange={(e) => setPersistAfterVerify(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          />
          <div>
            <label
              htmlFor="persist-after-verify-checkbox"
              className="text-sm font-medium text-gray-900 cursor-pointer block"
            >
              {STRINGS.remediation.preview.persistLabel}
            </label>
            <p className="text-xs text-gray-500 mt-0.5">
              {STRINGS.remediation.preview.persistHelp}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end space-x-3 pt-3 border-t border-gray-200">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            {STRINGS.common.cancel}
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting
              ? STRINGS.remediation.preview.submitting
              : STRINGS.remediation.preview.submitPropose}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
