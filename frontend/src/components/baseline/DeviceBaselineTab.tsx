import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { BaselineOut, DriftReportOut, DriftHistoryItemOut } from "../../types/api";
import {
  getActiveBaseline,
  retireActiveBaseline,
  getDrift,
  getDriftHistory,
} from "../../services/auditsApi";
import { BaselineCard } from "./BaselineCard";
import { DriftSummary } from "./DriftSummary";
import { DriftDetail } from "./DriftDetail";
import { DriftHistory } from "./DriftHistory";
import { Spinner } from "../ui/Spinner";
import { ApiClientError } from "../../services/apiClient";
import { STRINGS } from "../../i18n/strings";

interface DeviceBaselineTabProps {
  deviceId: string;
}

export function DeviceBaselineTab({ deviceId }: DeviceBaselineTabProps): React.JSX.Element {
  const queryClient = useQueryClient();

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailReport, setDetailReport] = useState<DriftReportOut | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Active baseline query
  const {
    data: baseline,
    isLoading: isBaselineLoading,
  } = useQuery<BaselineOut | null>({
    queryKey: ["active-baseline", deviceId],
    queryFn: () => getActiveBaseline(deviceId),
  });

  // Drift summary query for latest audit
  const {
    data: driftReport,
    isLoading: isDriftLoading,
  } = useQuery<DriftReportOut | null>({
    queryKey: ["drift-report", deviceId],
    queryFn: () => getDrift(deviceId),
    enabled: !!baseline,
  });

  // Drift history query
  const {
    data: driftHistory = [],
  } = useQuery<DriftHistoryItemOut[]>({
    queryKey: ["drift-history", deviceId],
    queryFn: () => getDriftHistory(deviceId),
    enabled: !!baseline,
  });

  // Retire mutation
  const retireMutation = useMutation({
    mutationFn: () => retireActiveBaseline(deviceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["active-baseline", deviceId] });
      void queryClient.invalidateQueries({ queryKey: ["drift-report", deviceId] });
      void queryClient.invalidateQueries({ queryKey: ["drift-history", deviceId] });
    },
  });

  const handleRetire = async (): Promise<void> => {
    if (!window.confirm(STRINGS.baseline.retireConfirm)) return;
    try {
      await retireMutation.mutateAsync();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Không thể gỡ baseline.");
    }
  };

  const handleViewDetail = async (): Promise<void> => {
    setIsLoadingDetail(true);
    setDetailError(null);
    try {
      const res = await getDrift(deviceId, undefined, true);
      setDetailReport(res);
      setIsDetailOpen(true);
    } catch (err: unknown) {
      if (
        (err instanceof ApiClientError && (err.code === "CONTENT_DISABLED" || err.status === 403)) ||
        (err instanceof Error && (err.message.includes("CONTENT_DISABLED") || err.message.includes("403")))
      ) {
        setDetailError(STRINGS.drift.contentDisabled);
      } else {
        const msg = err instanceof Error ? err.message : String(err);
        setDetailError(msg || "Không thể tải chi tiết dòng thay đổi.");
      }
    } finally {
      setIsLoadingDetail(false);
    }
  };

  if (isBaselineLoading) {
    return (
      <div className="py-12 flex flex-col items-center justify-center space-y-2 text-gray-500">
        <Spinner size="md" className="text-indigo-600" />
        <span className="text-xs">{STRINGS.common.loading}</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {detailError && (
        <div className="p-3 bg-amber-50 border border-amber-200 text-xs text-amber-800 rounded-lg flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>{detailError}</span>
        </div>
      )}

      {/* Baseline Card */}
      <BaselineCard
        baseline={baseline || null}
        onRetire={handleRetire}
        isRetiring={retireMutation.isPending}
      />

      {/* Drift Section (only when baseline exists) */}
      {baseline && (
        <>
          {isDriftLoading ? (
            <div className="py-6 flex justify-center">
              <Spinner size="sm" className="text-indigo-600" />
            </div>
          ) : (
            <DriftSummary
              report={driftReport || null}
              onViewDetail={handleViewDetail}
              isLoadingDetail={isLoadingDetail}
            />
          )}

          {/* Drift History */}
          <DriftHistory history={driftHistory} />
        </>
      )}

      {/* Drift Detail Modal */}
      <DriftDetail
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        report={detailReport}
      />
    </div>
  );
}
