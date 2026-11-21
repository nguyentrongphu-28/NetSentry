import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { useDevices } from "../hooks/useDevices";
import { DeviceWithLatestAuditOut } from "../types/api";
import { STRINGS } from "../i18n/strings";
import { SummaryTiles } from "../components/devices/SummaryTiles";
import { DeviceTable } from "../components/devices/DeviceTable";
import { AddDeviceDialog } from "../components/devices/AddDeviceDialog";
import { DeleteDeviceDialog } from "../components/devices/DeleteDeviceDialog";
import { RunAuditDialog } from "../components/devices/RunAuditDialog";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { useCan } from "../auth/useCan";

export function DevicesPage(): React.JSX.Element {
  const { data, isLoading, isError, error, refetch } = useDevices();
  const canCreate = useCan("device:create");

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [deviceToDelete, setDeviceToDelete] = useState<DeviceWithLatestAuditOut | null>(null);
  const [deviceToAudit, setDeviceToAudit] = useState<DeviceWithLatestAuditOut | null>(null);
  const [backgroundNotice, setBackgroundNotice] = useState<{
    runId: number;
    deviceId: string;
  } | null>(null);

  const devices = data?.items || [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            {STRINGS.dashboard.title}
          </h1>
          <p className="mt-1 text-sm text-gray-500">{STRINGS.dashboard.subtitle}</p>
        </div>
        {canCreate && (
          <div>
            <Button
              variant="primary"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setIsAddOpen(true)}
            >
              {STRINGS.dashboard.addDevice}
            </Button>
          </div>
        )}
      </div>

      {/* Background completed notice */}
      {backgroundNotice && (
        <div
          role="status"
          className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center justify-between text-sm text-emerald-800"
        >
          <span>
            Tiến trình audit thiết bị <strong>{backgroundNotice.deviceId}</strong> đã hoàn tất.
          </span>
          <Link
            to={`/audits/${backgroundNotice.runId}`}
            className="font-medium text-emerald-700 underline hover:text-emerald-900 ml-3"
          >
            Xem kết quả chi tiết
          </Link>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Spinner size="lg" className="text-indigo-600" />
          <p className="text-sm text-gray-500">{STRINGS.dashboard.loading}</p>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <ErrorBanner
          title={STRINGS.dashboard.errorLoad}
          message={error instanceof Error ? error.message : "Lỗi không xác định."}
          onRetry={() => refetch()}
        />
      )}

      {/* Content when loaded */}
      {!isLoading && !isError && (
        <>
          {/* Summary stats */}
          <SummaryTiles devices={devices} />

          {/* Table or Empty state */}
          {devices.length === 0 ? (
            <EmptyState
              title={STRINGS.dashboard.emptyTitle}
              description={STRINGS.dashboard.emptyDescription}
              actionText={canCreate ? STRINGS.dashboard.emptyAction : undefined}
              onAction={canCreate ? () => setIsAddOpen(true) : undefined}
            />
          ) : (
            <DeviceTable
              devices={devices}
              onRunAudit={(d) => setDeviceToAudit(d)}
              onDeleteDevice={(d) => setDeviceToDelete(d)}
            />
          )}
        </>
      )}

      {/* Add Device Dialog */}
      <AddDeviceDialog isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} />

      {/* Delete Device Dialog */}
      <DeleteDeviceDialog
        device={deviceToDelete}
        isOpen={Boolean(deviceToDelete)}
        onClose={() => setDeviceToDelete(null)}
      />

      {/* Run Audit Dialog */}
      <RunAuditDialog
        device={deviceToAudit}
        isOpen={Boolean(deviceToAudit)}
        onClose={() => setDeviceToAudit(null)}
        onAuditCompletedInBackground={(runId, deviceId) =>
          setBackgroundNotice({ runId, deviceId })
        }
      />
    </div>
  );
}
