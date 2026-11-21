import React from "react";
import { Badge, BadgeVariant } from "../ui/Badge";
import { RemediationPlanStatus } from "../../types/api";
import { STRINGS } from "../../i18n/strings";

interface PlanStatusBadgeProps {
  status: RemediationPlanStatus;
}

export function PlanStatusBadge({ status }: PlanStatusBadgeProps): React.JSX.Element {
  const label = STRINGS.remediation.statuses[status] || status;

  let variant: BadgeVariant = "neutral";

  switch (status) {
    case "APPROVED":
    case "APPLIED":
    case "VERIFIED":
      variant = "success";
      break;
    case "PROPOSED":
    case "APPLYING":
      variant = "info";
      break;
    case "REJECTED":
    case "CANCELLED":
    case "EXPIRED":
      variant = "neutral";
      break;
    case "VERIFY_FAILED":
    case "FAILED":
    case "ROLLED_BACK":
      variant = "danger";
      break;
  }

  return <Badge variant={variant}>{label}</Badge>;
}
