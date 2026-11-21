import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, ArrowLeftRight, Trash2, Shield, Eye, AlertCircle } from "lucide-react";
import { SnapshotOut, ConfigDiffOut } from "../../types/api";
import {
  listDeviceSnapshots,
  getSnapshot,
  getDeviceConfigDiff,
  deleteSnapshot,
} from "../../services/auditsApi";
import { Button } from "../ui/Button";
import { Spinner } from "../ui/Spinner";
import { Modal } from "../ui/Modal";
import { ErrorBanner } from "../ui/ErrorBanner";
import { DiffViewer } from "./DiffViewer";
import { formatDateTime } from "../../utils/format";
import { STRINGS } from "../../i18n/strings";
import { useCan } from "../../auth/useCan";

interface SnapshotListProps {
  deviceId: string;
}

export function SnapshotList({ deviceId }: SnapshotListProps): React.JSX.Element {
  const queryClient = useQueryClient();
  const canDelete = useCan("device:delete");

  // Selection for Diff (by run_id)
  const [selectedFirstRun, setSelectedFirstRun] = useState<number | null>(null);
  const [selectedSecondRun, setSelectedSecondRun] = useState<number | null>(null);
  const [diffResult, setDiffResult] = useState<ConfigDiffOut | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);
  const [isDiffModalOpen, setIsDiffModalOpen] = useState(false);

  // Content Modal
  const [viewSnapshot, setViewSnapshot] = useState<{ id: number; content: string } | null>(null);
  const [isContentLoading, setIsContentLoading] = useState(false);
  const [contentError, setContentError] = useState<string | null>(null);

  const {
    data: snapshots = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<SnapshotOut[], Error>({
    queryKey: ["device-snapshots", deviceId],
    queryFn: () => listDeviceSnapshots(deviceId),
  });

  const deleteMutation = useMutation({
    mutationFn: (snapshotId: number) => deleteSnapshot(snapshotId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["device-snapshots", deviceId] });
    },
  });

  const handleViewContent = async (snapshotId: number): Promise<void> => {
    setIsContentLoading(true);
    setContentError(null);
    try {
      const detail = await getSnapshot(snapshotId);
      setViewSnapshot({ id: detail.id, content: detail.content });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("CONTENT_DISABLED") || msg.includes("403")) {
        setContentError(STRINGS.snapshots.contentDisabled);
      } else {
        setContentError(msg || "Không thể tải nội dung snapshot.");
      }
    } finally {
      setIsContentLoading(false);
    }
  };

  const handleRunDiff = async (): Promise<void> => {
    if (!selectedFirstRun || !selectedSecondRun) return;
    setIsDiffLoading(true);
    setContentError(null);
    try {
      const res = await getDeviceConfigDiff(deviceId, selectedFirstRun, selectedSecondRun);
      setDiffResult(res);
      setIsDiffModalOpen(true);
    } catch (err) {
      setContentError(err instanceof Error ? err.message : "Không thể so sánh 2 snapshot.");
    } finally {
      setIsDiffLoading(false);
    }
  };

  const handleDelete = async (snapshotId: number): Promise<void> => {
    if (!window.confirm(STRINGS.snapshots.deleteConfirm)) return;
    try {
      await deleteMutation.mutateAsync(snapshotId);
      if (selectedFirstRun === snapshotId) setSelectedFirstRun(null);
      if (selectedSecondRun === snapshotId) setSelectedSecondRun(null);
    } catch (err) {
      setContentError(err instanceof Error ? err.message : "Không thể xóa snapshot.");
    }
  };

  if (isLoading) {
    return (
      <div className="py-12 flex flex-col items-center justify-center space-y-2 text-gray-500">
        <Spinner size="md" className="text-indigo-600" />
        <span className="text-xs">{STRINGS.common.loading}</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {isError && (
        <ErrorBanner
          title="Lỗi tải danh sách snapshots"
          message={error?.message || "Không thể tải danh sách snapshots"}
          onRetry={() => void refetch()}
        />
      )}

      {contentError && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-xs text-rose-700 rounded-lg flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
          <span>{contentError}</span>
        </div>
      )}

      {/* Action bar for Diff */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between bg-slate-50 border border-slate-200 rounded-lg p-3 gap-2">
        <div className="flex items-center space-x-2 text-xs text-gray-600">
          <ArrowLeftRight className="w-4 h-4 text-indigo-600" />
          <span>
            {STRINGS.snapshots.diffTitle}:{" "}
            {selectedFirstRun ? `Run #${selectedFirstRun}` : "(Chưa chọn 1)"} vs{" "}
            {selectedSecondRun ? `Run #${selectedSecondRun}` : "(Chưa chọn 2)"}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={!selectedFirstRun && !selectedSecondRun}
            onClick={() => {
              setSelectedFirstRun(null);
              setSelectedSecondRun(null);
            }}
          >
            Bỏ chọn
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<ArrowLeftRight className="w-3.5 h-3.5" />}
            disabled={!selectedFirstRun || !selectedSecondRun || selectedFirstRun === selectedSecondRun}
            isLoading={isDiffLoading}
            onClick={handleRunDiff}
          >
            {STRINGS.snapshots.diffTitle}
          </Button>
        </div>
      </div>

      {snapshots.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-xs text-gray-400">
          <Camera className="w-8 h-8 text-gray-300 mx-auto mb-2" />
          <p>{STRINGS.snapshots.empty}</p>
        </div>
      ) : (
        <div className="overflow-x-auto border border-gray-200 rounded-xl bg-white shadow-xs">
          <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
            <thead className="bg-gray-50/75 text-gray-500 font-semibold">
              <tr>
                <th className="py-2.5 px-3">ID / Run</th>
                <th className="py-2.5 px-3">{STRINGS.snapshots.colTime}</th>
                <th className="py-2.5 px-3">{STRINGS.snapshots.colLines}</th>
                <th className="py-2.5 px-3">{STRINGS.snapshots.colSize}</th>
                <th className="py-2.5 px-3">{STRINGS.snapshots.colSha}</th>
                <th className="py-2.5 px-3 text-right">{STRINGS.snapshots.colActions}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 font-normal">
              {snapshots.map((s) => {
                const isFirst = selectedFirstRun === s.run_id;
                const isSecond = selectedSecondRun === s.run_id;

                return (
                  <tr
                    key={s.id}
                    className={`hover:bg-gray-50/60 transition-colors ${
                      isFirst || isSecond ? "bg-indigo-50/40" : ""
                    }`}
                  >
                    <td className="py-2.5 px-3 font-medium text-gray-900">
                      <div className="flex items-center space-x-1.5">
                        <Camera className="w-3.5 h-3.5 text-gray-400" />
                        <span>#{s.id}</span>
                        {s.run_id && (
                          <span className="text-[10px] text-indigo-600 bg-indigo-50 px-1 py-0.2 rounded border border-indigo-200">
                            Run #{s.run_id}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-gray-600">
                      {formatDateTime(s.created_at)}
                    </td>
                    <td className="py-2.5 px-3 text-gray-600 font-mono">
                      {s.line_count.toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-gray-600 font-mono">
                      {(s.size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[10px] text-gray-400">
                      {s.content_sha256 ? s.content_sha256.substring(0, 12) + "..." : "-"}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            if (isFirst) setSelectedFirstRun(null);
                            else setSelectedFirstRun(s.run_id);
                          }}
                          className={`px-1.5 py-0.5 text-[10px] rounded border font-medium ${
                            isFirst
                              ? "bg-indigo-600 text-white border-indigo-600"
                              : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                          }`}
                          title="Chọn làm bản 1 để so sánh"
                        >
                          1
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (isSecond) setSelectedSecondRun(null);
                            else setSelectedSecondRun(s.run_id);
                          }}
                          className={`px-1.5 py-0.5 text-[10px] rounded border font-medium ${
                            isSecond
                              ? "bg-indigo-600 text-white border-indigo-600"
                              : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                          }`}
                          title="Chọn làm bản 2 để so sánh"
                        >
                          2
                        </button>
                        <Button
                          variant="ghost"
                          size="sm"
                          isLoading={isContentLoading}
                          icon={<Eye className="w-3.5 h-3.5" />}
                          onClick={() => handleViewContent(s.id)}
                          title={STRINGS.snapshots.viewContent}
                        />
                        {canDelete && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-rose-600 hover:text-rose-800 hover:bg-rose-50"
                            icon={<Trash2 className="w-3.5 h-3.5" />}
                            onClick={() => handleDelete(s.id)}
                            title="Xóa snapshot"
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Snapshot Content Modal */}
      <Modal
        isOpen={viewSnapshot !== null}
        onClose={() => setViewSnapshot(null)}
        title={`Nội dung Snapshot #${viewSnapshot?.id || ""}`}
        maxWidth="lg"
      >
        <div className="space-y-3">
          <div className="flex items-center space-x-2 text-xs text-amber-700 bg-amber-50 p-2 rounded border border-amber-200">
            <Shield className="w-4 h-4 flex-shrink-0" />
            <span>Cấu hình đã được che mật khẩu, secret và chuẩn hóa trước khi lưu.</span>
          </div>
          <pre className="p-4 bg-slate-900 text-slate-100 rounded-lg text-[11px] font-mono overflow-x-auto max-h-[500px] leading-5 select-text">
            {viewSnapshot?.content}
          </pre>
        </div>
      </Modal>

      {/* Diff Modal */}
      <Modal
        isOpen={isDiffModalOpen}
        onClose={() => setIsDiffModalOpen(false)}
        title={`${STRINGS.snapshots.diffTitle}: Run #${diffResult?.from_run_id} vs #${diffResult?.to_run_id}`}
        maxWidth="xl"
      >
        {diffResult && <DiffViewer diff={diffResult} />}
      </Modal>
    </div>
  );
}
