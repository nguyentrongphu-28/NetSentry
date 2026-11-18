import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Play } from "lucide-react";
import { useDevice } from "../hooks/useDevice";
import { useAuditRuns } from "../hooks/useAuditRuns";
import { AuditHistoryTable } from "../components/audits/AuditHistoryTable";
import { RunAuditDialog } from "../components/devices/RunAuditDialog";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { StatusBadge } from "../components/audits/StatusBadge";
import { formatDateTime } from "../utils/format";
import { STRINGS } from "../i18n/strings";

export function DeviceDetailPage(): React.JSX.Element {
  const { deviceId } = useParams<{ deviceId: string }>();
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const [isRunAuditOpen, setIsRunAuditOpen] = useState(false);

  const {
    data: device,
    isLoading: isDeviceLoading,
    isError: isDeviceError,
    error: deviceError,
    refetch: refetchDevice,
  } = useDevice(deviceId);

  const {
    data: auditsData,
    isLoading: isAuditsLoading,
    isError: isAuditsError,
    error: auditsError,
    refetch: refetchAudits,
  } = useAuditRuns(deviceId, limit, offset);

  if (isDeviceLoading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <Spinner size="lg" className="text-indigo-600" />
        <p className="text-sm text-gray-500">Đang tải thông tin thiết bị...</p>
      </div>
    );
  }

  if (isDeviceError || !device) {
    return (
      <div className="space-y-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>{STRINGS.nav.backToDashboard}</span>
        </Link>
        <ErrorBanner
          title="Không tìm thấy thiết bị"
          message={deviceError instanceof Error ? deviceError.message : "Thiết bị không tồn tại."}
          onRetry={() => refetchDevice()}
        />
      </div>
    );
  }

  const latestAudit = device.latest_audit;

  return (
    <div className="space-y-6">
      {/* Back button */}
      <div>
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{STRINGS.nav.backToDashboard}</span>
        </Link>
      </div>

      {/* Header with actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              {device.device_id}
            </h1>
            <span className="bg-gray-100 text-gray-700 font-mono text-xs px-2 py-0.5 rounded border border-gray-200">
              {device.platform}
            </span>
          </div>
          {device.name && (
            <p className="text-sm text-gray-500 mt-1">{device.name}</p>
          )}
        </div>

        <div>
          <Button
            variant="primary"
            icon={<Play className="w-4 h-4 fill-current" />}
            onClick={() => setIsRunAuditOpen(true)}
          >
            {STRINGS.deviceDetail.runAuditBtn}
          </Button>
        </div>
      </div>

      {/* Device Info & Latest Audit Summary Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Info card */}
        <div className="md:col-span-2 bg-white rounded-xl border border-gray-200 p-6 shadow-xs space-y-4">
          <h2 className="text-sm font-semibold text-gray-900 border-b border-gray-100 pb-3">
            {STRINGS.deviceDetail.infoCardTitle}
          </h2>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <span className="text-gray-500 block">{STRINGS.deviceDetail.fieldHost}</span>
              <span className="font-semibold text-gray-900 font-mono mt-0.5 block">
                {device.host}
              </span>
            </div>

            <div>
              <span className="text-gray-500 block">{STRINGS.deviceDetail.fieldPort}</span>
              <span className="font-semibold text-gray-900 font-mono mt-0.5 block">
                {device.port}
              </span>
            </div>

            <div>
              <span className="text-gray-500 block">{STRINGS.deviceDetail.fieldPlatform}</span>
              <span className="font-semibold text-gray-900 mt-0.5 block">
                {device.platform}
              </span>
            </div>

            <div>
              <span className="text-gray-500 block">{STRINGS.deviceDetail.fieldCreatedAt}</span>
              <span className="text-gray-700 mt-0.5 block">
                {formatDateTime(device.created_at)}
              </span>
            </div>

            <div>
              <span className="text-gray-500 block">{STRINGS.deviceDetail.fieldUpdatedAt}</span>
              <span className="text-gray-700 mt-0.5 block">
                {formatDateTime(device.updated_at)}
              </span>
            </div>
          </div>
        </div>

        {/* Latest Audit Card */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 border-b border-gray-100 pb-3">
              Lần kiểm toán gần nhất
            </h2>

            {latestAudit ? (
              <div className="mt-4 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Trạng thái:</span>
                  <StatusBadge status={latestAudit.status} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Thời gian:</span>
                  <span className="text-gray-800 font-medium">
                    {formatDateTime(latestAudit.started_at)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Kết quả:</span>
                  <div className="flex items-center space-x-1.5 font-mono text-[11px]">
                    <span className="text-emerald-700 font-bold">{latestAudit.pass_count}P</span>
                    <span className="text-gray-300">/</span>
                    <span className="text-rose-700 font-bold">{latestAudit.fail_count}F</span>
                    <span className="text-gray-300">/</span>
                    <span className="text-amber-700 font-bold">{latestAudit.unknown_count}U</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-gray-400">
                Chưa từng chạy kiểm toán
              </div>
            )}
          </div>

          {latestAudit && (
            <div className="pt-4 border-t border-gray-100">
              <Link
                to={`/audits/${latestAudit.id}`}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold hover:underline block text-center"
              >
                Xem chi tiết lần audit #{latestAudit.id} →
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Audit History Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">
              {STRINGS.deviceDetail.historyTitle}
            </h2>
            <p className="text-xs text-gray-500">
              {STRINGS.deviceDetail.historySubtitle}
            </p>
          </div>
        </div>

        {isAuditsError ? (
          <ErrorBanner
            title="Lỗi tải lịch sử audit"
            message={auditsError instanceof Error ? auditsError.message : "Không thể tải lịch sử."}
            onRetry={() => refetchAudits()}
          />
        ) : (
          <AuditHistoryTable
            audits={auditsData?.items || []}
            total={auditsData?.total || 0}
            limit={limit}
            offset={offset}
            onPageChange={(newOffset) => setOffset(newOffset)}
            isLoading={isAuditsLoading}
          />
        )}
      </div>

      {/* Run Audit Dialog */}
      <RunAuditDialog
        device={device}
        isOpen={isRunAuditOpen}
        onClose={() => setIsRunAuditOpen(false)}
      />
    </div>
  );
}
