import {
  ApprovePlanIn,
  ProposePlanIn,
  RejectPlanIn,
  RemediationPlanDetailOut,
  RemediationPlanOut,
  TemplatesResponseOut,
} from "../types/api";
import { apiFetch } from "./apiClient";

export async function getRemediationTemplates(): Promise<TemplatesResponseOut> {
  return apiFetch<TemplatesResponseOut>("/api/v1/remediation/templates");
}

export async function proposeRemediationPlan(
  runId: number,
  ruleId: string,
  payload: ProposePlanIn
): Promise<RemediationPlanOut> {
  return apiFetch<RemediationPlanOut>(
    `/api/v1/audits/${runId}/findings/${encodeURIComponent(ruleId)}/remediation`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function listDeviceRemediationPlans(
  deviceId: string,
  status?: string
): Promise<RemediationPlanOut[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch<RemediationPlanOut[]>(
    `/api/v1/devices/${encodeURIComponent(deviceId)}/remediation-plans${query}`
  );
}

export async function getRemediationPlan(
  planId: number
): Promise<RemediationPlanDetailOut> {
  return apiFetch<RemediationPlanDetailOut>(
    `/api/v1/remediation-plans/${planId}`
  );
}

export async function approveRemediationPlan(
  planId: number,
  payload: ApprovePlanIn
): Promise<RemediationPlanDetailOut> {
  return apiFetch<RemediationPlanDetailOut>(
    `/api/v1/remediation-plans/${planId}/approve`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function rejectRemediationPlan(
  planId: number,
  payload: RejectPlanIn
): Promise<RemediationPlanDetailOut> {
  return apiFetch<RemediationPlanDetailOut>(
    `/api/v1/remediation-plans/${planId}/reject`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function cancelRemediationPlan(
  planId: number
): Promise<RemediationPlanDetailOut> {
  return apiFetch<RemediationPlanDetailOut>(
    `/api/v1/remediation-plans/${planId}/cancel`,
    {
      method: "POST",
    }
  );
}
