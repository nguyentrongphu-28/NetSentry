import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { ErrorBanner } from "../ui/ErrorBanner";
import { isApiErrorResponse } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { approveRemediationPlan } from "../../services/remediationApi";
import { ApiClientError } from "../../services/apiClient";
import { ShieldCheck } from "lucide-react";

interface ApproveDialogProps {
  isOpen: boolean;
  onClose: () => void;
  planId: number;
  onSuccess: () => void;
}

export function ApproveDialog({
  isOpen,
  onClose,
  planId,
  onSuccess,
}: ApproveDialogProps): React.JSX.Element {
  const [password, setPassword] = useState("");
  const [confirmed, setConfirmed] = useState(false);
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
    return "Đã xảy ra lỗi khi duyệt kế hoạch.";
  };

  const handleClose = () => {
    setPassword("");
    setConfirmed(false);
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!confirmed || !password) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await approveRemediationPlan(planId, { password });
      setPassword(""); // Clear immediately from memory
      handleClose();
      onSuccess();
    } catch (err) {
      setPassword(""); // Always clear password on failure
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={STRINGS.remediation.approve.title}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorBanner message={error} />}

        <div className="rounded-lg bg-sky-50 p-3.5 border border-sky-200 flex items-start space-x-2.5">
          <ShieldCheck className="w-5 h-5 text-sky-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-sky-800 leading-relaxed">
            Hành động này yêu cầu quyền Quản trị viên (Admin) và xác thực lại danh tính. Mật khẩu của bạn không được lưu lại dưới bất kỳ hình thức nào.
          </p>
        </div>

        {/* Step-up password input */}
        <div>
          <label
            htmlFor="approve-stepup-password"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            {STRINGS.remediation.approve.passwordLabel}
          </label>
          <input
            id="approve-stepup-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={STRINGS.remediation.approve.passwordPlaceholder}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            required
            disabled={isSubmitting}
          />
        </div>

        {/* Confirmation Checkbox */}
        <div className="pt-2 flex items-start space-x-2.5">
          <input
            id="approve-confirm-checkbox"
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            required
            disabled={isSubmitting}
          />
          <label
            htmlFor="approve-confirm-checkbox"
            className="text-sm font-medium text-gray-900 select-none cursor-pointer"
          >
            {STRINGS.remediation.approve.confirmCheckbox}
          </label>
        </div>

        {/* Actions */}
        <div className="flex justify-end space-x-3 pt-3 border-t border-gray-200">
          <Button type="button" variant="secondary" onClick={handleClose} disabled={isSubmitting}>
            {STRINGS.common.cancel}
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!confirmed || !password || isSubmitting}
          >
            {isSubmitting
              ? STRINGS.remediation.approve.approving
              : STRINGS.remediation.approve.btnApprove}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
