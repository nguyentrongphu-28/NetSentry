import React from "react";
import { STRINGS } from "../../i18n/strings";
import { AuditRunStatus, FindingStatus } from "../../types/api";

export interface StatusBadgeProps {
  status: AuditRunStatus | FindingStatus;
  size?: "sm" | "md";
  className?: string;
}

export function StatusBadge({
  status,
  size = "md",
  className = "",
}: StatusBadgeProps): React.JSX.Element {
  const config = {
    PASS: {
      label: STRINGS.badges.pass,
      classes: "bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/20",
      dot: "bg-emerald-500",
    },
    FAIL: {
      label: STRINGS.badges.fail,
      classes: "bg-rose-50 text-rose-700 border-rose-200 ring-rose-500/20",
      dot: "bg-rose-500",
    },
    UNKNOWN: {
      label: STRINGS.badges.unknown,
      classes: "bg-amber-50 text-amber-700 border-amber-200 ring-amber-500/20",
      dot: "bg-amber-500",
    },
    COMPLETED: {
      label: STRINGS.badges.completed,
      classes: "bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/20",
      dot: "bg-emerald-500",
    },
    FAILED: {
      label: STRINGS.badges.failed,
      classes: "bg-rose-50 text-rose-700 border-rose-200 ring-rose-500/20",
      dot: "bg-rose-500",
    },
  }[status] || {
    label: status,
    classes: "bg-gray-50 text-gray-700 border-gray-200 ring-gray-500/20",
    dot: "bg-gray-500",
  };

  const sizeClasses = size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-x-1.5 rounded-md font-semibold border ${sizeClasses} ${config.classes} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      <span>{config.label}</span>
    </span>
  );
}
