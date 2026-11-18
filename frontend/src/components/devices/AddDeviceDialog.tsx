import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { STRINGS } from "../../i18n/strings";
import { useCreateDevice } from "../../hooks/useCreateDevice";
import { ApiClientError } from "../../services/apiClient";

export interface AddDeviceDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const DEVICE_ID_REGEX = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

export function AddDeviceDialog({
  isOpen,
  onClose,
}: AddDeviceDialogProps): React.JSX.Element {
  const [deviceId, setDeviceId] = useState("");
  const [host, setHost] = useState("");
  const [name, setName] = useState("");
  const [port, setPort] = useState(22);

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  const createMutation = useCreateDevice();

  const resetForm = (): void => {
    setDeviceId("");
    setHost("");
    setName("");
    setPort(22);
    setFieldErrors({});
    setGeneralError(null);
  };

  const handleClose = (): void => {
    resetForm();
    onClose();
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    const trimmedId = deviceId.trim();
    if (!trimmedId) {
      errors.device_id = "Vui lòng nhập mã thiết bị.";
    } else if (!DEVICE_ID_REGEX.test(trimmedId)) {
      errors.device_id =
        "Mã thiết bị phải từ 1-64 ký tự, bắt đầu bằng chữ/số, chỉ chứa chữ, số, '.', '_', '-'.";
    }

    const trimmedHost = host.trim();
    if (!trimmedHost) {
      errors.host = "Vui lòng nhập địa chỉ IP hoặc Hostname.";
    } else if (/\s|\//.test(trimmedHost)) {
      errors.host = "Địa chỉ host không được chứa khoảng trắng hoặc ký tự '/'.";
    }

    if (isNaN(port) || port < 1 || port > 65535) {
      errors.port = "Cổng SSH phải là số từ 1 đến 65535.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setGeneralError(null);

    if (!validate()) {
      return;
    }

    try {
      await createMutation.mutateAsync({
        device_id: deviceId.trim(),
        host: host.trim(),
        name: name.trim() || null,
        port: Number(port),
        platform: "cisco_ios",
      });
      handleClose();
    } catch (err: unknown) {
      const apiErr = err as ApiClientError;
      if (apiErr?.status === 409 || apiErr?.code === "DEVICE_EXISTS") {
        setFieldErrors((prev) => ({
          ...prev,
          device_id: STRINGS.addDeviceDialog.errorExists,
        }));
      } else if (apiErr?.status === 422 && apiErr.details) {
        const mapped: Record<string, string> = {};
        for (const d of apiErr.details) {
          mapped[d.field] = d.message;
        }
        setFieldErrors(mapped);
        setGeneralError(apiErr.message || STRINGS.addDeviceDialog.errorInvalid);
      } else {
        setGeneralError(apiErr?.message || "Không thể tạo thiết bị.");
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={STRINGS.addDeviceDialog.title}
      description={STRINGS.addDeviceDialog.description}
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} type="button">
            {STRINGS.addDeviceDialog.cancel}
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            isLoading={createMutation.isPending}
            type="submit"
          >
            {STRINGS.addDeviceDialog.submit}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {generalError && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700">
            {generalError}
          </div>
        )}

        {/* Device ID */}
        <div>
          <label htmlFor="device-id-input" className="block text-xs font-semibold text-gray-700">
            {STRINGS.addDeviceDialog.deviceIdLabel} *
          </label>
          <input
            id="device-id-input"
            type="text"
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
            placeholder={STRINGS.addDeviceDialog.deviceIdPlaceholder}
            className={`mt-1 block w-full px-3 py-2 text-sm border rounded-md shadow-xs focus:outline-none focus:ring-1 ${
              fieldErrors.device_id
                ? "border-rose-300 focus:ring-rose-500 focus:border-rose-500"
                : "border-gray-300 focus:ring-indigo-500 focus:border-indigo-500"
            }`}
          />
          {fieldErrors.device_id ? (
            <p className="mt-1 text-xs text-rose-600">{fieldErrors.device_id}</p>
          ) : (
            <p className="mt-1 text-xs text-gray-400">{STRINGS.addDeviceDialog.deviceIdHelp}</p>
          )}
        </div>

        {/* Host and Port */}
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label htmlFor="device-host-input" className="block text-xs font-semibold text-gray-700">
              {STRINGS.addDeviceDialog.hostLabel} *
            </label>
            <input
              id="device-host-input"
              type="text"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder={STRINGS.addDeviceDialog.hostPlaceholder}
              className={`mt-1 block w-full px-3 py-2 text-sm border rounded-md shadow-xs focus:outline-none focus:ring-1 ${
                fieldErrors.host
                  ? "border-rose-300 focus:ring-rose-500 focus:border-rose-500"
                  : "border-gray-300 focus:ring-indigo-500 focus:border-indigo-500"
              }`}
            />
            {fieldErrors.host && (
              <p className="mt-1 text-xs text-rose-600">{fieldErrors.host}</p>
            )}
          </div>

          <div>
            <label htmlFor="device-port-input" className="block text-xs font-semibold text-gray-700">
              {STRINGS.addDeviceDialog.portLabel} *
            </label>
            <input
              id="device-port-input"
              type="number"
              min={1}
              max={65535}
              value={port}
              onChange={(e) => setPort(Number(e.target.value))}
              className={`mt-1 block w-full px-3 py-2 text-sm border rounded-md shadow-xs focus:outline-none focus:ring-1 ${
                fieldErrors.port
                  ? "border-rose-300 focus:ring-rose-500 focus:border-rose-500"
                  : "border-gray-300 focus:ring-indigo-500 focus:border-indigo-500"
              }`}
            />
            {fieldErrors.port && (
              <p className="mt-1 text-xs text-rose-600">{fieldErrors.port}</p>
            )}
          </div>
        </div>

        {/* Name */}
        <div>
          <label htmlFor="device-name-input" className="block text-xs font-semibold text-gray-700">
            {STRINGS.addDeviceDialog.nameLabel}
          </label>
          <input
            id="device-name-input"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={STRINGS.addDeviceDialog.namePlaceholder}
            className="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>

        {/* Platform (fixed) */}
        <div>
          <label htmlFor="device-platform-input" className="block text-xs font-semibold text-gray-700">
            {STRINGS.addDeviceDialog.platformLabel}
          </label>
          <input
            id="device-platform-input"
            type="text"
            value={STRINGS.addDeviceDialog.platformFixed}
            readOnly
            disabled
            className="mt-1 block w-full px-3 py-2 text-sm bg-gray-100 border border-gray-200 text-gray-600 rounded-md cursor-not-allowed"
          />
        </div>
      </form>
    </Modal>
  );
}
