import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, CheckCircle } from "lucide-react";
import { AttentionPlanOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { acknowledgeAttention } from "../../services/remediationApi";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { formatDateTime } from "../../utils/format";
import { useAuth } from "../../auth/AuthProvider";

interface ManualAttentionListProps {
  attentionList: AttentionPlanOut[];
  onRefresh: () => void;
}

export function ManualAttentionList({
  attentionList,
  onRefresh,
}: ManualAttentionListProps): React.JSX.Element | null {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [selectedExec, setSelectedExec] = useState<AttentionPlanOut | null>(null);
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!attentionList || attentionList.length === 0) return null;

  const handleOpenAck = (item: AttentionPlanOut) => {
    setSelectedExec(item);
    setNote("");
    setError(null);
  };

  const handleCloseAck = () => {
    setSelectedExec(null);
    setNote("");
    setError(null);
  };

  const handleSubmitAck = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExec) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await acknowledgeAttention(selectedExec.execution_id, {
        note: note.trim() || undefined,
      });
      handleCloseAck();
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi khi cập nhật trạng thái.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-red-50 dark:bg-red-950/40 border-2 border-red-500 rounded-lg p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-red-600 dark:text-red-400" />
          <h3 className="font-bold text-red-900 dark:text-red-200 text-sm uppercase tracking-wide">
            {STRINGS.remediation.attention.title}
          </h3>
          <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-red-600 text-white">
            {attentionList.length}
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {attentionList.map((item) => (
          <div
            key={item.execution_id}
            className="bg-white dark:bg-gray-800 p-4 rounded border border-red-200 dark:border-red-900/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono font-bold text-sm text-gray-900 dark:text-gray-100">
                  {item.device_id}
                </span>
                <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 font-mono text-gray-700 dark:text-gray-300">
                  {item.rule_id}
                </span>
                <Link
                  to={`/remediation-plans/${item.plan_id}`}
                  className="text-xs text-primary-600 hover:underline font-medium"
                >
                  Kế hoạch #{item.plan_id}
                </Link>
                <span className="text-xs text-gray-400">
                  (Exec #{item.execution_id})
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Bắt đầu: {formatDateTime(item.started_at)}
                {item.failure_code && ` • Lỗi: ${item.failure_code}`}
                {item.changes_sent && (
                  <span className="text-red-600 dark:text-red-400 font-medium ml-1">
                    [Cấu hình đã gửi tới thiết bị]
                  </span>
                )}
              </p>
            </div>

            {isAdmin && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleOpenAck(item)}
                className="shrink-0 text-xs border-red-300 hover:bg-red-50 dark:hover:bg-red-950 text-red-700 dark:text-red-300"
              >
                <CheckCircle className="w-3.5 h-3.5 mr-1" />
                {STRINGS.remediation.attention.ackBtn}
              </Button>
            )}
          </div>
        ))}
      </div>

      {/* Acknowledge Modal */}
      {selectedExec && (
        <Modal
          isOpen={true}
          onClose={handleCloseAck}
          title={STRINGS.remediation.attention.ackDialogTitle}
        >
          <form onSubmit={handleSubmitAck} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-100 text-red-800 text-xs rounded">
                {error}
              </div>
            )}
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Xác nhận bạn đã kiểm tra và xử lý thủ công thiết bị{" "}
              <strong className="font-mono text-gray-900 dark:text-gray-100">
                {selectedExec.device_id}
              </strong>{" "}
              cho lần thực thi #{selectedExec.execution_id}.
            </p>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">
                {STRINGS.remediation.attention.ackNoteLabel}
              </label>
              <textarea
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={STRINGS.remediation.attention.ackNotePlaceholder}
                className="w-full px-3 py-2 text-sm border rounded bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={handleCloseAck}
                disabled={isSubmitting}
              >
                {STRINGS.common.cancel}
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={isSubmitting}
              >
                {isSubmitting
                  ? STRINGS.remediation.attention.ackSubmitting
                  : STRINGS.remediation.attention.ackConfirm}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
