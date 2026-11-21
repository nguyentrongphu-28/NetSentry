import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { ErrorBanner } from "../ui/ErrorBanner";
import { ExecutionMode, RemediationPlanDetailOut, isApiErrorResponse } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { applyRemediationPlan } from "../../services/remediationApi";
import { ApiClientError } from "../../services/apiClient";
import { AlertTriangle, Play, ShieldAlert, Undo2 } from "lucide-react";

interface ApplyDialogProps {
  isOpen: boolean;
  onClose: () => void;
  plan: RemediationPlanDetailOut;
  executionMode: ExecutionMode;
  onSuccess: (execId: number, mode: string) => void;
}

export function ApplyDialog({
  isOpen,
  onClose,
  plan,
  executionMode,
  onSuccess,
}: ApplyDialogProps): React.JSX.Element {
  const [confirmDevice, setConfirmDevice] = useState("");
  const [password, setPassword] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDryRun = executionMode === "dry_run";
  const deviceMismatch = confirmDevice.length > 0 && confirmDevice.trim() !== plan.device_id;
  const isFormValid =
    confirmed &&
    password.length > 0 &&
    confirmDevice.trim() === plan.device_id &&
    !isSubmitting;

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
    return "Đã xảy ra lỗi khi thực thi kế hoạch.";
  };

  const handleClose = () => {
    setConfirmDevice("");
    setPassword("");
    setConfirmed(false);
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!isFormValid) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const resp = await applyRemediationPlan(plan.id, {
        confirm_device_id: confirmDevice.trim(),
        password,
      });
      setPassword(""); // Clear immediately
      handleClose();
      onSuccess(resp.execution_id, resp.mode);
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
      title={
        isDryRun
          ? STRINGS.remediation.execute.dialogTitleDryRun
          : STRINGS.remediation.execute.dialogTitleLive
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorBanner message={error} />}

        {/* Commands list */}
        <div>
          <div className="block text-xs font-semibold uppercase text-gray-500 mb-1">
            {STRINGS.remediation.execute.commandsToExecute}
          </div>
          <div className="bg-gray-900 text-green-400 font-mono text-xs p-3 rounded space-y-1 overflow-x-auto border border-gray-700">
            {plan.commands.map((cmd, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-gray-500 select-none">$</span>
                <span>{cmd}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Rollback note / commands */}
        {plan.reversible && plan.rollback_commands && plan.rollback_commands.length > 0 ? (
          <div>
            <div className="block text-xs font-semibold uppercase text-gray-500 mb-1 flex items-center gap-1">
              <Undo2 className="w-3.5 h-3.5 text-blue-500" />
              <span>{STRINGS.remediation.execute.rollbackCommandsTitle}</span>
            </div>
            <div className="bg-gray-900 text-yellow-300 font-mono text-xs p-2.5 rounded space-y-1 overflow-x-auto border border-gray-700">
              {plan.rollback_commands.map((cmd, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-gray-500 select-none">#</span>
                  <span>{cmd}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded flex gap-2.5 items-start">
            <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 dark:text-amber-300">
              {STRINGS.remediation.execute.irreversibleWarning}
            </p>
          </div>
        )}

        {/* Device Confirmation */}
        <div>
          <label
            htmlFor="confirm-device"
            className="block text-xs font-semibold uppercase text-gray-500 mb-1"
          >
            {`${STRINGS.remediation.execute.confirmDeviceLabel} (${plan.device_id})`}
          </label>
          <input
            id="confirm-device"
            type="text"
            required
            autoComplete="off"
            value={confirmDevice}
            onChange={(e) => setConfirmDevice(e.target.value)}
            placeholder={STRINGS.remediation.execute.confirmDevicePlaceholder}
            className="w-full px-3 py-2 text-sm border rounded bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          {deviceMismatch && (
            <p className="text-xs text-red-600 mt-1">
              {STRINGS.remediation.execute.confirmDeviceMismatch}
            </p>
          )}
        </div>

        {/* Password */}
        <div>
          <label
            htmlFor="admin-password"
            className="block text-xs font-semibold uppercase text-gray-500 mb-1"
          >
            {STRINGS.remediation.execute.passwordLabel}
          </label>
          <input
            id="admin-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={STRINGS.remediation.execute.passwordPlaceholder}
            className="w-full px-3 py-2 text-sm border rounded bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Confirm Checkbox */}
        <div className="flex items-start gap-2 pt-1">
          <input
            id="confirm-apply"
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="mt-0.5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          <label
            htmlFor="confirm-apply"
            className="text-xs text-gray-700 dark:text-gray-300 cursor-pointer"
          >
            {isDryRun
              ? STRINGS.remediation.execute.confirmCheckboxDryRun
              : STRINGS.remediation.execute.confirmCheckboxLive}
          </label>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2 pt-3 border-t border-gray-200 dark:border-gray-700">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            {STRINGS.common.cancel}
          </Button>
          <Button
            type="submit"
            variant={isDryRun ? "secondary" : "danger"}
            disabled={!isFormValid}
            className="flex items-center gap-1.5"
          >
            {isDryRun ? (
              <Play className="w-4 h-4" />
            ) : (
              <ShieldAlert className="w-4 h-4" />
            )}
            {isSubmitting
              ? STRINGS.remediation.execute.submitting
              : isDryRun
              ? STRINGS.remediation.execute.btnSubmitDryRun
              : STRINGS.remediation.execute.btnSubmitApply}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
