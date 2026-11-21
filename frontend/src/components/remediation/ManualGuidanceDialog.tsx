import React from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { ManualGuidanceOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { Info, AlertTriangle, CheckCircle2 } from "lucide-react";

interface ManualGuidanceDialogProps {
  isOpen: boolean;
  onClose: () => void;
  guidance: ManualGuidanceOut | null;
}

export function ManualGuidanceDialog({
  isOpen,
  onClose,
  guidance,
}: ManualGuidanceDialogProps): React.JSX.Element {
  if (!guidance) return <></>;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${STRINGS.remediation.manual.title} - ${guidance.rule_id}`}
    >
      <div className="space-y-4">
        <div>
          <h4 className="text-base font-medium text-gray-900">{guidance.title}</h4>
        </div>

        <div className="rounded-lg bg-amber-50 p-3.5 border border-amber-200 flex items-start space-x-2.5">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <h5 className="text-sm font-semibold text-amber-800">
              {STRINGS.remediation.manual.whyNotAutomated}
            </h5>
            <p className="mt-1 text-sm text-amber-700">{guidance.why_not_automated}</p>
          </div>
        </div>

        <div className="rounded-lg bg-sky-50 p-3.5 border border-sky-200 flex items-start space-x-2.5">
          <Info className="w-5 h-5 text-sky-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <h5 className="text-sm font-semibold text-sky-800">
              {STRINGS.remediation.manual.remediationGuide}
            </h5>
            <div className="mt-1 font-mono text-xs bg-white p-2.5 rounded border border-sky-200 text-sky-900 whitespace-pre-wrap">
              {guidance.remediation_guide}
            </div>
          </div>
        </div>

        <div className="rounded-lg bg-emerald-50 p-3.5 border border-emerald-200 flex items-start space-x-2.5">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <h5 className="text-sm font-semibold text-emerald-800">
              {STRINGS.remediation.manual.verificationGuide}
            </h5>
            <div className="mt-1 font-mono text-xs bg-white p-2.5 rounded border border-emerald-200 text-emerald-900 whitespace-pre-wrap">
              {guidance.verification_guide}
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>
            {STRINGS.common.close}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
