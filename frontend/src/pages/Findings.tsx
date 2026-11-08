import { useMemo, useState } from "react";
import { api } from "../api/client";
import AiExplain from "../components/AiExplain";
import { Card, CodeBlock, Empty, ErrorBox, Loading, SeverityBadge } from "../components/ui";
import { fmtTime, useAsync } from "../hooks";
import type { Finding, FindingStatus, Severity } from "../types";

const SEVS: Array<Severity | "all"> = ["all", "critical", "high", "medium", "low", "info"];
const STATUSES: Array<FindingStatus | "all"> = ["all", "open", "resolved", "accepted", "false_positive"];

export default function Findings() {
  const { data, error, loading, reload } = useAsync(() => api.listFindings(), []);
  const [sev, setSev] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<FindingStatus | "all">("open");
  const [selected, setSelected] = useState<Finding | null>(null);

  const rows = useMemo(() => (data ?? []).filter((f) => (sev === "all" || f.severity === sev) && (status === "all" || f.status === status)), [data, sev, status]);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <>
      <h1>Findings</h1>
      <div className="row filters">
        <label>Severity <select className="input" value={sev} onChange={(e) => setSev(e.target.value as Severity | "all")}>{SEVS.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label>Status <select className="input" value={status} onChange={(e) => setStatus(e.target.value as FindingStatus | "all")}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></label>
        <span className="muted small">{rows.length} shown</span>
      </div>
      <div className="split">
        <Card>
          {rows.length === 0 ? <Empty>No findings match these filters.</Empty> : (
            <table><thead><tr><th>Rule</th><th>Title</th><th>Severity</th><th>Status</th></tr></thead>
              <tbody>{rows.map((f) => (
                <tr key={f.rule_id + f.scan_id} className={`clickable ${selected === f ? "sel" : ""}`} tabIndex={0}
                  onClick={() => setSelected(f)} onKeyDown={(e) => e.key === "Enter" && setSelected(f)}>
                  <td>{f.rule_id}</td><td>{f.title}<div className="muted small">{f.device_id}</div></td><td><SeverityBadge severity={f.severity} /></td><td>{f.status}</td>
                </tr>))}</tbody></table>
          )}
        </Card>
        <div>
          {!selected ? <Card><Empty>Select a finding to see evidence and remediation guidance.</Empty></Card> : (
            <>
              <Card title={`${selected.rule_id} — ${selected.title}`}>
                <p><SeverityBadge severity={selected.severity} /> <span className="muted small">checked {fmtTime(selected.checked_at)} on {selected.device_id}</span></p>
                <h4>Evidence</h4><CodeBlock lines={selected.evidence} />
                <h4>Rationale</h4><p>{selected.rationale}</p>
                <h4>Remediation guidance</h4><p>{selected.remediation}</p>
              </Card>
              <AiExplain key={selected.rule_id + selected.scan_id} finding={selected} />
            </>
          )}
        </div>
      </div>
    </>
  );
}
