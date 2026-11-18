import React from "react";
import { STRINGS } from "../../i18n/strings";
import { FindingSeverity } from "../../types/api";

export interface SeverityBadgeProps {
  severity: FindingSeverity;
  className?: string;
}

export function SeverityBadge({
  severity,
  className = "",
}: SeverityBadgeProps): React.JSX.Element {
  const config = {
    CRITICAL: {
      label: STRINGS.badges.critical,
      classes: "bg-red-100 text-red-800 border-red-300 font-bold",
    },
    HIGH: {
      label: STRINGS.badges.high,
      classes: "bg-rose-100 text-rose-800 border-rose-300 font-semibold",
    },
    MEDIUM: {
      label: STRINGS.badges.medium,
      classes: "bg-amber-100 text-amber-800 border-amber-300 font-medium",
    },
    LOW: {
      label: STRINGS.badges.low,
      classes: "bg-blue-100 text-blue-800 border-blue-300 font-medium",
    },
    INFO: {
      label: STRINGS.badges.info,
      classes: "bg-gray-100 text-gray-800 border-gray-300 font-medium",
    },
  }[severity] || {
    label: severity,
    classes: "bg-gray-100 text-gray-800 border-gray-300",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${config.classes} ${className}`}
    >
      {config.label}
    </span>
  );
}
