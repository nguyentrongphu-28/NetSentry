import type { Api } from "./client";
import { ApiError } from "./errors";
import { diffLines } from "./diff";
import { auditLogs, devices, findings, scans, snapshots } from "../mock/data";
import type { ActionType, ExplainResponse, Finding, RemediationJob } from "../types";

const delay = <T,>(v: T, ms = 250) => new Promise<T>((r) => setTimeout(() => r(v), ms));
const jobs = new Map<string, RemediationJob>();
let seq = 100;

const UPLINKS = ["Gi0/0"];
const ALLOWED: ActionType[] = ["create_vlan", "configure_access_port"];

/** Mirrors what backend validation should do (client-side mock only). */
function buildPreview(action: ActionType, p: Record<string, string>): { lines: string[]; errors: string[] } {
  const errors: string[] = [];
  if (action === "create_vlan") {
    const id = Number(p.vlan_id);
    if (!Number.isInteger(id) || id < 2 || id > 4094) errors.push("vlan_id must be an integer between 2 and 4094");
    if (id >= 1002 && id <= 1005) errors.push("VLAN IDs 1002-1005 are reserved");
    if (!/^[A-Za-z0-9_-]{1,32}$/.test(p.vlan_name ?? "")) errors.push("vlan_name must be 1-32 chars: letters, digits, '_' or '-'");
    return { lines: errors.length ? [] : [`vlan ${id}`, ` name ${p.vlan_name}`], errors };
  }
  if (!/^(Gi|Fa)\d+\/\d+$/.test(p.interface ?? "")) errors.push("interface must look like Gi0/3 or Fa0/5");
  if (UPLINKS.includes(p.interface ?? "")) errors.push(`${p.interface} is flagged as an uplink in this lab; changes are blocked`);
  const v = Number(p.vlan_id);
  if (!Number.isInteger(v) || v < 2 || v > 4094) errors.push("vlan_id must be an integer between 2 and 4094");
  return {
    lines: errors.length ? [] : [`interface ${p.interface}`, " switchport mode access", ` switchport access vlan ${v}`],
    errors,
  };
}

function need(id: string): RemediationJob {
  const j = jobs.get(id);
  if (!j) throw new ApiError(404, "Job not found");
  return j;
}

function explainMock(finding: Finding): ExplainResponse {
  return {
    provider: "mock",
    rejected_reason: null,
    explanation: {
      summary: `${finding.title}. Based on the evidence, the configuration matches rule ${finding.rule_id}.`,
      why_it_matters: finding.rationale,
      evidence_refs: finding.evidence,
      suggested_action: null,
      suggested_params: {},
      confidence: "medium",
      caveats: ["This is a configuration finding; actual exposure was not verified.", "Review against your baseline before changing anything."],
    },
  };
}

export const mockApi: Api = {
  listDevices: () => delay([...devices]),
  getDevice: async (id) => {
    const d = devices.find((x) => x.device_id === id);
    if (!d) throw new ApiError(404, "Device not found");
    return delay(d);
  },
  testConnection: async (id) => {
    const d = devices.find((x) => x.device_id === id);
    if (!d) throw new ApiError(404, "Device not found");
    return delay(d, 800);
  },
  runScan: async (id) => {
    const s = { scan_id: `scan-${++seq}`, device_id: id, started_at: new Date().toISOString(), finished_at: new Date().toISOString(), status: "completed" as const, duration_seconds: 5, findings_count: findings.filter((f) => f.device_id === id && f.status === "open").length, error: null };
    scans.unshift(s);
    return delay(s, 900);
  },
  listScans: (id) => delay(scans.filter((s) => !id || s.device_id === id)),
  listFindings: (p) => delay(findings.filter((f) => (!p?.deviceId || f.device_id === p.deviceId) && (!p?.scanId || f.scan_id === p.scanId))),
  listSnapshots: (id) => delay(snapshots.filter((s) => s.device_id === id)),
  takeSnapshot: async () => delay(snapshots[0], 600),
  getDiff: async (id, from, to) => {
    const a = snapshots.find((s) => s.snapshot_id === from);
    const b = snapshots.find((s) => s.snapshot_id === to);
    if (!a || !b) throw new ApiError(404, "Snapshot not found");
    return delay({ device_id: id, from_snapshot_id: from, to_snapshot_id: to, lines: diffLines(a.content, b.content) });
  },
  listAuditLogs: () => delay([...auditLogs]),

  previewRemediation: async (req) => {
    if (!ALLOWED.includes(req.action_type)) throw new ApiError(400, `Action '${req.action_type}' is not in the allowlist`);
    const { lines, errors } = buildPreview(req.action_type, req.params);
    const job: RemediationJob = {
      job_id: `job-${++seq}`, action_type: req.action_type, target_device: req.target_device,
      params: req.params, preview: lines, validation_errors: errors,
      approval_status: "pending", execution_status: "not_started", verification_result: null,
      created_at: new Date().toISOString(),
    };
    jobs.set(job.job_id, job);
    return delay({ ...job });
  },
  approveRemediation: async (id) => {
    const j = need(id);
    if (j.validation_errors.length) throw new ApiError(409, "Cannot approve a job with validation errors");
    j.approval_status = "approved";
    return delay({ ...j });
  },
  rejectRemediation: async (id) => { const j = need(id); j.approval_status = "rejected"; return delay({ ...j }); },
  executeRemediation: async (id) => {
    const j = need(id);
    if (j.approval_status !== "approved") throw new ApiError(409, "Job is not approved; execution blocked");
    j.execution_status = "succeeded";
    return delay({ ...j }, 1200);
  },
  verifyRemediation: async (id) => {
    const j = need(id);
    if (j.execution_status !== "succeeded") throw new ApiError(409, "Nothing to verify: job has not executed");
    j.verification_result = { passed: true, detail: "Post-change 'show running-config' contains the expected lines." };
    return delay({ ...j });
  },
  explainFinding: async ({ finding }) => delay(explainMock(finding), 700),
};
