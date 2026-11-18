import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Spinner } from "../ui/Spinner";
import { STRINGS } from "../../i18n/strings";
import { DeviceWithLatestAuditOut, AuditRequestPayload } from "../../types/api";
import { useRunAudit } from "../../hooks/useRunAudit";
import { ApiClientError } from "../../services/apiClient";

export interface RunAuditDialogProps {
  device: DeviceWithLatestAuditOut | null;
  isOpen: boolean;
  onClose: () => void;
  onAuditCompletedInBackground?: (runId: number, deviceId: string) => void;
}

export function RunAuditDialog({
  device,
  isOpen,
  onClose,
  onAuditCompletedInBackground,
}: RunAuditDialogProps): React.JSX.Element {
  const navigate = useNavigate();
  const runMutation = useRunAudit();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [enableSecret, setEnableSecret] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  const isClosedByUserRef = useRef(false);

  const clearSecretsAndReset = (): void => {
    setUsername("");
    setPassword("");
    setEnableSecret("");
    setFieldErrors({});
    setGeneralError(null);
    runMutation.reset();
  };

  const handleClose = (): void => {
    if (runMutation.isPending) {
      isClosedByUserRef.current = true;
    }
    clearSecretsAndReset();
    onClose();
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!username.trim()) {
      errors.username = "Vui lòng nhập tên đăng nhập SSH.";
    }
    if (!password) {
      errors.password = "Vui lòng nhập mật khẩu SSH.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (runMutation.isPending) return;

    setGeneralError(null);

    if (!device) return;
    if (!validate()) return;

    isClosedByUserRef.current = false;

    const payload: AuditRequestPayload = {
      credentials: {
        username: username.trim(),
        password,
        ...(enableSecret ? { enable_secret: enableSecret } : {}),
      },
    };

    try {
      const result = await runMutation.mutateAsync({
        deviceId: device.device_id,
        payload,
      });

      // If user closed dialog while mutation was in flight: do not navigate
      if (isClosedByUserRef.current) {
        clearSecretsAndReset();
        onAuditCompletedInBackground?.(result.summary.id, device.device_id);
        return;
      }

      // Clear secrets immediately after mutation finishes
      clearSecretsAndReset();
      onClose();

      // Navigate to audit detail page on 201 (even if run status is FAILED)
      navigate(`/audits/${result.summary.id}`);
    } catch (err: unknown) {
      // Clear password states on error as well
      setPassword("");
      setEnableSecret("");
      runMutation.reset();

      const apiErr = err as ApiClientError;
      if (apiErr?.code === "VALIDATION_ERROR" && apiErr.details) {
        const mapped: Record<string, string> = {};
        for (const d of apiErr.details) {
          if (d.field) {
            mapped[d.field] = d.message;
          }
        }
        setFieldErrors(mapped);
        setGeneralError(apiErr.message || "Dữ liệu nhập không hợp lệ.");
      } else if (apiErr?.code === "CREDENTIALS_REQUIRED" || apiErr?.status === 422) {
        setGeneralError(STRINGS.runAuditDialog.errorCredentialsRequired);
      } else if (apiErr?.status === 409 || apiErr?.code === "AUDIT_ALREADY_RUNNING") {
        setGeneralError(STRINGS.runAuditDialog.errorAlreadyRunning);
      } else if (apiErr?.status === 404 || apiErr?.code === "DEVICE_NOT_FOUND") {
        setGeneralError(STRINGS.runAuditDialog.errorDeviceNotFound);
      } else if (apiErr?.code === "CLIENT_TIMEOUT") {
        setGeneralError(STRINGS.runAuditDialog.timeoutNotice);
      } else {
        setGeneralError(apiErr?.message || "Không thể thực hiện kiểm toán.");
      }
    }
  };

  const isPending = runMutation.isPending;

  return (
    <Modal
      isOpen={isOpen && Boolean(device)}
      onClose={handleClose}
      title={STRINGS.runAuditDialog.title}
      description={STRINGS.runAuditDialog.description}
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} type="button">
            {STRINGS.runAuditDialog.cancel}
          </Button>
          <Button
            variant="primary"
            isLoading={isPending}
            disabled={isPending}
            onClick={handleSubmit}
            type="submit"
            form="run-audit-form"
          >
            {isPending ? "Đang chạy..." : STRINGS.runAuditDialog.submit}
          </Button>
        </>
      }
    >
      <form id="run-audit-form" onSubmit={handleSubmit} className="space-y-4">
        <button type="submit" className="hidden" tabIndex={-1} aria-hidden="true" />
        {/* Device Info */}
        <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 flex items-center justify-between">
          <span className="text-gray-500">Mục tiêu kiểm toán:</span>
          <span className="font-semibold text-gray-900">{device?.device_id}</span>
        </div>

        {generalError && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700">
            {generalError}
          </div>
        )}

        {/* Running status banner */}
        {isPending && (
          <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg space-y-2">
            <div className="flex items-center space-x-2 text-indigo-700 text-sm font-medium">
              <Spinner size="sm" className="text-indigo-600" />
              <span>{STRINGS.runAuditDialog.runningStatus}</span>
            </div>
            <p className="text-xs text-indigo-600">{STRINGS.runAuditDialog.runningNotice}</p>
          </div>
        )}

        {/* Username */}
        <div>
          <label htmlFor="audit-username-input" className="block text-xs font-semibold text-gray-700">
            {STRINGS.runAuditDialog.usernameLabel} *
          </label>
          <input
            id="audit-username-input"
            type="text"
            autoComplete="off"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isPending}
            placeholder={STRINGS.runAuditDialog.usernamePlaceholder}
            className={`mt-1 block w-full px-3 py-2 text-sm border rounded-md shadow-xs focus:outline-none focus:ring-1 ${
              fieldErrors.username
                ? "border-rose-300 focus:ring-rose-500 focus:border-rose-500"
                : "border-gray-300 focus:ring-indigo-500 focus:border-indigo-500"
            }`}
          />
          {fieldErrors.username && (
            <p className="mt-1 text-xs text-rose-600">{fieldErrors.username}</p>
          )}
        </div>

        {/* Password */}
        <div>
          <label htmlFor="audit-password-input" className="block text-xs font-semibold text-gray-700">
            {STRINGS.runAuditDialog.passwordLabel} *
          </label>
          <input
            id="audit-password-input"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isPending}
            placeholder={STRINGS.runAuditDialog.passwordPlaceholder}
            className={`mt-1 block w-full px-3 py-2 text-sm border rounded-md shadow-xs focus:outline-none focus:ring-1 ${
              fieldErrors.password
                ? "border-rose-300 focus:ring-rose-500 focus:border-rose-500"
                : "border-gray-300 focus:ring-indigo-500 focus:border-indigo-500"
            }`}
          />
          {fieldErrors.password && (
            <p className="mt-1 text-xs text-rose-600">{fieldErrors.password}</p>
          )}
        </div>

        {/* Enable Secret */}
        <div>
          <label
            htmlFor="audit-enable-secret-input"
            className="block text-xs font-semibold text-gray-700"
          >
            {STRINGS.runAuditDialog.enableSecretLabel}
          </label>
          <input
            id="audit-enable-secret-input"
            type="password"
            autoComplete="new-password"
            value={enableSecret}
            onChange={(e) => setEnableSecret(e.target.value)}
            disabled={isPending}
            placeholder={STRINGS.runAuditDialog.enableSecretPlaceholder}
            className="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
          />
          {fieldErrors.enable_secret && (
            <p className="mt-1 text-xs text-rose-600">{fieldErrors.enable_secret}</p>
          )}
        </div>

        <p className="text-xs text-gray-500">{STRINGS.runAuditDialog.securityNote}</p>
      </form>
    </Modal>
  );
}
