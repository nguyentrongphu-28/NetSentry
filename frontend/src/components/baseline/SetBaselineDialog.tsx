import React, { useState } from "react";
import { AlertTriangle, CheckCircle } from "lucide-react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { STRINGS } from "../../i18n/strings";

interface SetBaselineDialogProps {
  isOpen: boolean;
  onClose: () => void;
  snapshotId: number;
  failCount?: number;
  onConfirm: (payload: { note: string; confirmWithFailures: boolean }) => Promise<void>;
  isLoading?: boolean;
}

export function SetBaselineDialog({
  isOpen,
  onClose,
  snapshotId,
  failCount = 0,
  onConfirm,
  isLoading = false,
}: SetBaselineDialogProps): React.JSX.Element {
  const [note, setNote] = useState("");
  const [confirmedFailures, setConfirmedFailures] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detectedFailures, setDetectedFailures] = useState(false);
  const [detectedCount, setDetectedCount] = useState<number>(failCount);

  const effectiveCount = detectedCount > 0 ? detectedCount : failCount;
  const hasFailures = effectiveCount > 0 || detectedFailures;
  const canSubmit = !hasFailures || confirmedFailures;

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    try {
      await onConfirm({
        note: note.trim(),
        confirmWithFailures: confirmedFailures,
      });
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Không thể đặt làm baseline.";
      setError(msg);
      if (
        msg.includes("BASELINE_FAILURES_NOT_CONFIRMED") ||
        msg.includes("failing findings") ||
        msg.includes("409")
      ) {
        setDetectedFailures(true);
        const match = msg.match(/(\d+)\s+failing/);
        if (match && match[1]) {
          setDetectedCount(Number(match[1]));
        }
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${STRINGS.baseline.dialogTitle} #${snapshotId}`}
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        {hasFailures ? (
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
            <div className="flex items-start space-x-2 text-amber-800">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <span>
                {STRINGS.baseline.dialogConfirmWarning.replace("{count}", String(effectiveCount || "một số"))}
              </span>
            </div>
            <div className="flex items-center space-x-2 pt-1">
              <input
                id="baseline-confirm-failures"
                type="checkbox"
                checked={confirmedFailures}
                onChange={(e) => setConfirmedFailures(e.target.checked)}
                className="rounded border-amber-400 text-indigo-600 focus:ring-indigo-500"
              />
              <label
                htmlFor="baseline-confirm-failures"
                className="font-medium text-amber-950 cursor-pointer select-none"
              >
                {STRINGS.baseline.dialogConfirmCheckbox}
              </label>
            </div>
          </div>
        ) : (
          <div className="flex items-center space-x-2 p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800">
            <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>Lượt audit của snapshot này đạt chuẩn bảo mật (0 lỗi FAIL).</span>
          </div>
        )}

        <div>
          <label htmlFor="baseline-note-input" className="block font-medium text-gray-700 mb-1">
            {STRINGS.baseline.noteLabel}
          </label>
          <textarea
            id="baseline-note-input"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={200}
            rows={3}
            placeholder={STRINGS.baseline.notePlaceholder}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-1 focus:ring-indigo-500 focus:outline-none"
          />
          <span className="text-[10px] text-gray-400 block text-right">
            {note.length}/200 ký tự
          </span>
        </div>

        {error && (
          <div className="p-2 bg-rose-50 border border-rose-200 text-rose-700 rounded text-xs">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-100">
          <Button variant="secondary" size="sm" type="button" onClick={onClose} disabled={isLoading}>
            {STRINGS.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="sm"
            type="submit"
            disabled={!canSubmit}
            isLoading={isLoading}
          >
            {STRINGS.common.confirm}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
