import { useState } from "react";
import { api } from "../api/client";
import { Card, CodeBlock, ErrorBox, Pill } from "../components/ui";
import { useAsync } from "../hooks";
import type { ActionType, RemediationJob } from "../types";

const FIELDS: Record<ActionType, Array<{ key: string; label: string; placeholder: string }>> = {
  create_vlan: [
    { key: "vlan_id", label: "VLAN ID", placeholder: "20" },
    { key: "vlan_name", label: "VLAN name", placeholder: "GUESTS" },
  ],
  configure_access_port: [
    { key: "interface", label: "Interface", placeholder: "Gi0/3" },
    { key: "vlan_id", label: "Access VLAN", placeholder: "10" },
  ],
};

const STEPS = ["Preview", "Approve", "Execute", "Verify"] as const;

function stepIndex(j: RemediationJob | null): number {
  if (!j) return 0;
  if (j.verification_result) return 4;
  if (j.execution_status === "succeeded") return 3;
  if (j.approval_status === "approved") return 2;
  return 1;
}

export default function Remediation() {
  const devs = useAsync(() => api.listDevices(), []);
  const [action, setAction] = useState<ActionType>("create_vlan");
  const [device, setDevice] = useState("");
  const [params, setParams] = useState<Record<string, string>>({});
  const [job, setJob] = useState<RemediationJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const call = async (fn: () => Promise<RemediationJob>) => {
    setBusy(true); setError(null);
    try { setJob(await fn()); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const reset = () => { setJob(null); setError(null); };
  const switches = (devs.data ?? []).filter((d) => d.role === "switch");
  const step = stepIndex(job);
  const rejected = job?.approval_status === "rejected";

  return (
    <>
      <h1>Remediation</h1>
      <p className="muted">Controlled change workflow: Preview → Validate → Approve → Execute → Verify. Only allowlisted actions are available. Use lab ports/VLANs only — never uplinks or production networks.</p>
      <ol className="stepper" aria-label="Workflow progress">
        {STEPS.map((s, i) => <li key={s} className={i < step ? "done" : i === step ? "current" : ""}>{s}</li>)}
      </ol>

      <Card title="1. Request a change">
        <div className="form">
          <label>Action
            <select className="input" value={action} disabled={!!job} onChange={(e) => { setAction(e.target.value as ActionType); setParams({}); }}>
              <option value="create_vlan">Create VLAN</option>
              <option value="configure_access_port">Configure access port</option>
            </select></label>
          <label>Target device (switches only)
            <select className="input" value={device} disabled={!!job} onChange={(e) => setDevice(e.target.value)}>
              <option value="">— select —</option>
              {switches.map((d) => <option key={d.device_id} value={d.device_id}>{d.hostname}</option>)}
            </select></label>
          {FIELDS[action].map((f) => (
            <label key={f.key}>{f.label}
              <input className="input" disabled={!!job} placeholder={f.placeholder} value={params[f.key] ?? ""}
                onChange={(e) => setParams({ ...params, [f.key]: e.target.value })} /></label>
          ))}
        </div>
        {!job && <button className="btn primary" disabled={busy || !device}
          onClick={() => call(() => api.previewRemediation({ action_type: action, target_device: device, params }))}>
          {busy ? "Generating…" : "Generate preview"}</button>}
        {job && <button className="btn" onClick={reset}>Start over</button>}
      </Card>

      {error && <ErrorBox message={error} />}

      {job && (
        <Card title="2. Preview & validation">
          {job.validation_errors.length > 0 ? (
            <div className="state error" role="alert"><strong>Validation failed — approval is blocked.</strong>
              <ul>{job.validation_errors.map((e, i) => <li key={i}>{e}</li>)}</ul></div>
          ) : (
            <>
              <p className="small">These exact commands will be sent to <strong>{job.target_device}</strong> (generated from a fixed template, not free text):</p>
              <CodeBlock lines={job.preview} />
            </>
          )}
          <p>Approval: <Pill tone={job.approval_status === "approved" ? "ok" : job.approval_status === "rejected" ? "bad" : "warn"}>{job.approval_status}</Pill>{" "}
            Execution: <Pill tone={job.execution_status === "succeeded" ? "ok" : job.execution_status === "failed" ? "bad" : "muted"}>{job.execution_status}</Pill></p>
          <div className="row">
            <button className="btn primary" disabled={busy || job.validation_errors.length > 0 || job.approval_status !== "pending"} onClick={() => call(() => api.approveRemediation(job.job_id))}>Approve</button>
            <button className="btn" disabled={busy || job.approval_status !== "pending"} onClick={() => call(() => api.rejectRemediation(job.job_id))}>Reject</button>
            <button className="btn danger" disabled={busy || job.approval_status !== "approved" || job.execution_status !== "not_started"}
              onClick={() => { if (window.confirm(`Send ${job.preview.length} commands to ${job.target_device}? A pre-change snapshot should already exist.`)) void call(() => api.executeRemediation(job.job_id)); }}>Execute</button>
            <button className="btn" disabled={busy || job.execution_status !== "succeeded" || !!job.verification_result} onClick={() => call(() => api.verifyRemediation(job.job_id))}>Verify</button>
          </div>
          {rejected && <p className="muted">Job rejected. Nothing was sent to the device.</p>}
          {job.verification_result && (
            <div className={`state ${job.verification_result.passed ? "" : "error"}`} role="status">
              Verification {job.verification_result.passed ? "passed" : "FAILED"}: {job.verification_result.detail}
            </div>
          )}
        </Card>
      )}
    </>
  );
}
