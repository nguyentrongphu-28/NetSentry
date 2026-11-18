import React from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { STRINGS } from "../../i18n/strings";
import { DeviceWithLatestAuditOut } from "../../types/api";
import { useDeleteDevice } from "../../hooks/useDeleteDevice";
import { AlertTriangle } from "lucide-react";
import { ApiClientError } from "../../services/apiClient";

export interface DeleteDeviceDialogProps {
  device: DeviceWithLatestAuditOut | null;
  isOpen: boolean;
  onClose: () => void;
}

export function DeleteDeviceDialog({
  device,
  isOpen,
  onClose,
}: DeleteDeviceDialogProps): React.JSX.Element {
  const deleteMutation = useDeleteDevice();

  const handleDelete = async (): Promise<void> => {
    if (!device) return;

    try {
      await deleteMutation.mutateAsync(device.device_id);
      onClose();
    } catch (err: unknown) {
      if (err instanceof ApiClientError && err.status === 404) {
        // 404 treated as already deleted
        onClose();
      } else {
        alert(err instanceof Error ? err.message : "Không thể xóa thiết bị.");
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen && Boolean(device)}
      onClose={onClose}
      title={STRINGS.deleteDeviceDialog.title}
      maxWidth="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} type="button">
            {STRINGS.deleteDeviceDialog.cancel}
          </Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            isLoading={deleteMutation.isPending}
            type="button"
          >
            {STRINGS.deleteDeviceDialog.confirm}
          </Button>
        </>
      }
    >
      <div className="flex items-start space-x-3">
        <div className="p-2 rounded-full bg-rose-100 text-rose-600 flex-shrink-0">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div>
          <p className="text-sm text-gray-700">
            {STRINGS.deleteDeviceDialog.confirmQuestion}{" "}
            <span className="font-bold text-gray-900">{device?.device_id}</span>?
          </p>
          <p className="mt-2 text-xs text-rose-600">
            {STRINGS.deleteDeviceDialog.warning}
          </p>
        </div>
      </div>
    </Modal>
  );
}
