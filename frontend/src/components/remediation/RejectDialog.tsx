import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { ErrorBanner } from "../ui/ErrorBanner";
import { isApiErrorResponse } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { rejectRemediationPlan } from "../../services/remediationApi";
import { ApiClientError } from "../../services/apiClient";

interface RejectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  planId: number;
  onSuccess: () => void;
}

export function RejectDialog({
  isOpen,
  onClose,
  planId,
  onSuccess,
}: RejectDialogProps): React.JSX.Element {
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    return "Đã xảy ra lỗi khi từ chối kế hoạch.";
  };

  const handleClose = () => {
    setReason("");
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    const cleanReason = reason.trim();
    if (!cleanReason) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await rejectRemediationPlan(planId, { reason: cleanReason });
      handleClose();
      onSuccess();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={STRINGS.remediation.reject.title}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorBanner message={error} />}

        <div>
          <label htmlFor="reject-reason-input" className="block text-sm font-medium text-gray-700 mb-1">
            {STRINGS.remediation.reject.reasonLabel}
          </label>
          <textarea
            id="reject-reason-input"
            value={reason}
            onChange={(e) => setReason(e.target.value.slice(0, 200))}
            placeholder={STRINGS.remediation.reject.reasonPlaceholder}
            rows={4}
            maxLength={200}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-rose-500 focus:outline-none focus:ring-1 focus:ring-rose-500"
            required
            disabled={isSubmitting}
          />
          <div className="text-right text-xs text-gray-400 mt-1">
            {reason.length}/200
          </div>
        </div>

        <div className="flex justify-end space-x-3 pt-3 border-t border-gray-200">
          <Button type="button" variant="secondary" onClick={handleClose} disabled={isSubmitting}>
            {STRINGS.common.cancel}
          </Button>
          <Button
            type="submit"
            variant="danger"
            disabled={!reason.trim() || isSubmitting}
          >
            {isSubmitting
              ? STRINGS.remediation.reject.rejecting
              : STRINGS.remediation.reject.btnReject}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
