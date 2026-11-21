import {
  AcknowledgeAttentionIn,
  ApplyPlanIn,
  ApplyResponseOut,
  ApprovePlanIn,
  AttentionPlanOut,
  ExecutionStatusOut,
  ProposePlanIn,
  RejectPlanIn,
  RemediationExecutionOut,
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

export async function getExecutionStatus(): Promise<ExecutionStatusOut> {
  return apiFetch<ExecutionStatusOut>("/api/v1/remediation/execution-status");
}

export async function applyRemediationPlan(
  planId: number,
  payload: ApplyPlanIn
): Promise<ApplyResponseOut> {
  return apiFetch<ApplyResponseOut>(
    `/api/v1/remediation-plans/${planId}/apply`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function listPlanExecutions(
  planId: number
): Promise<RemediationExecutionOut[]> {
  return apiFetch<RemediationExecutionOut[]>(
    `/api/v1/remediation-plans/${planId}/executions`
  );
}

export async function getPlanExecution(
  planId: number,
  executionId: number
): Promise<RemediationExecutionOut> {
  return apiFetch<RemediationExecutionOut>(
    `/api/v1/remediation-plans/${planId}/executions/${executionId}`
  );
}

export async function listAttentionPlans(): Promise<AttentionPlanOut[]> {
  return apiFetch<AttentionPlanOut[]>("/api/v1/remediation/attention");
}

export async function acknowledgeAttention(
  executionId: number,
  payload: AcknowledgeAttentionIn
): Promise<void> {
  await apiFetch<void>(
    `/api/v1/remediation/executions/${executionId}/acknowledge`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}
