import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card, Empty, ErrorBox, Loading, Pill } from "../components/ui";
import { fmtTime, useAsync } from "../hooks";
import type { Severity } from "../types";

const SEVS: Severity[] = ["critical", "high", "medium", "low", "info"];

export default function Dashboard() {
  const d = useAsync(() => api.listDevices(), []);
  const f = useAsync(() => api.listFindings(), []);
  const s = useAsync(() => api.listScans(), []);
  if (d.loading || f.loading || s.loading) return <Loading />;
  const err = d.error ?? f.error ?? s.error;
  if (err) return <ErrorBox message={err} onRetry={() => { d.reload(); f.reload(); s.reload(); }} />;
  const open = (f.data ?? []).filter((x) => x.status === "open");
  const reachable = (d.data ?? []).filter((x) => x.connection_status === "reachable").length;
  return (
    <>
      <h1>Dashboard</h1>
      <div className="grid4">
        <Card title="Devices"><div className="big">{reachable}/{d.data?.length ?? 0}</div><div className="muted small">reachable</div></Card>
        <Card title="Open findings"><div className="big">{open.length}</div><div className="muted small">across all devices</div></Card>
        {(["high", "medium"] as Severity[]).map((sv) => (
          <Card key={sv} title={`Open ${sv}`}><div className="big">{open.filter((x) => x.severity === sv).length}</div></Card>
        ))}
      </div>
      <Card title="Open findings by severity">
        {open.length === 0 ? <Empty>No open findings.</Empty> : (
          <div className="bars">
            {SEVS.map((sv) => {
              const n = open.filter((x) => x.severity === sv).length;
              return <div key={sv} className="barrow"><span className="barlabel">{sv}</span>
                <div className={`bar sev-${sv}`} style={{ width: `${Math.max(n * 60, n ? 8 : 0)}px` }} /><span>{n}</span></div>;
            })}
          </div>
        )}
      </Card>
      <Card title="Recent scans">
        {(s.data ?? []).length === 0 ? <Empty>No scans yet. Run one from the Devices page.</Empty> : (
          <table><thead><tr><th>Device</th><th>Started</th><th>Status</th><th>Duration</th><th>Findings</th></tr></thead>
            <tbody>{(s.data ?? []).slice(0, 5).map((x) => (
              <tr key={x.scan_id}>
                <td><Link to={`/devices/${x.device_id}`}>{x.device_id}</Link></td>
                <td>{fmtTime(x.started_at)}</td>
                <td><Pill tone={x.status === "completed" ? "ok" : x.status === "failed" ? "bad" : "warn"}>{x.status}</Pill>{x.error && <span className="muted small"> {x.error}</span>}</td>
                <td>{x.duration_seconds != null ? `${x.duration_seconds}s` : "—"}</td><td>{x.findings_count}</td>
              </tr>))}</tbody></table>
        )}
      </Card>
    </>
  );
}
