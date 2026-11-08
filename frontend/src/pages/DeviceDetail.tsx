import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Card, Empty, ErrorBox, Loading, Pill } from "../components/ui";
import { fmtTime, useAsync } from "../hooks";
import { SeverityBadge } from "../components/ui";
import type { SnapshotDiff } from "../types";

export default function DeviceDetail() {
  const { id = "" } = useParams();
  const dev = useAsync(() => api.getDevice(id), [id]);
  const snaps = useAsync(() => api.listSnapshots(id), [id]);
  const scans = useAsync(() => api.listScans(id), [id]);
  const fnd = useAsync(() => api.listFindings({ deviceId: id }), [id]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [diff, setDiff] = useState<SnapshotDiff | null>(null);
  const [diffErr, setDiffErr] = useState<string | null>(null);

  if (dev.loading) return <Loading />;
  if (dev.error || !dev.data) return <ErrorBox message={dev.error ?? "Device not found"} onRetry={dev.reload} />;
  const d = dev.data;
  const sl = snaps.data ?? [];

  const compare = async () => {
    setDiffErr(null); setDiff(null);
    if (!from || !to || from === to) { setDiffErr("Choose two different snapshots."); return; }
    try { setDiff(await api.getDiff(id, from, to)); } catch (e) { setDiffErr(e instanceof Error ? e.message : String(e)); }
  };

  return (
    <>
      <p><Link to="/devices">← Devices</Link></p>
      <h1>{d.hostname}</h1>
      <Card>
        <dl className="kv">
          <dt>IP</dt><dd>{d.ip_address}</dd><dt>Role</dt><dd>{d.role}</dd>
          <dt>Model</dt><dd>{d.model}</dd><dt>IOS</dt><dd>{d.ios_version}</dd>
          <dt>Connection</dt><dd><Pill tone={d.connection_status === "reachable" ? "ok" : "bad"}>{d.connection_status}</Pill> {d.last_error && <span className="err-text small">{d.last_error}</span>}</dd>
          <dt>Last scan</dt><dd>{fmtTime(d.last_scan_at)}</dd>
        </dl>
      </Card>

      <Card title="Findings on this device">
        {fnd.loading ? <Loading /> : (fnd.data ?? []).length === 0 ? <Empty>No findings recorded.</Empty> : (
          <table><thead><tr><th>Rule</th><th>Title</th><th>Severity</th><th>Status</th><th>Checked</th></tr></thead>
            <tbody>{(fnd.data ?? []).map((f) => (
              <tr key={f.rule_id + f.scan_id}><td>{f.rule_id}</td><td>{f.title}</td><td><SeverityBadge severity={f.severity} /></td><td>{f.status}</td><td>{fmtTime(f.checked_at)}</td></tr>))}</tbody></table>
        )}
      </Card>

      <Card title="Configuration snapshots">
        {snaps.loading ? <Loading /> : sl.length === 0 ? <Empty>No snapshots yet.</Empty> : (
          <>
            <table><thead><tr><th>ID</th><th>Taken</th><th>Lines</th></tr></thead>
              <tbody>{sl.map((s) => <tr key={s.snapshot_id}><td>{s.snapshot_id}</td><td>{fmtTime(s.taken_at)}</td><td>{s.line_count}</td></tr>)}</tbody></table>
            <div className="row" style={{ marginTop: 12 }}>
              <label>From <select className="input" value={from} onChange={(e) => setFrom(e.target.value)}><option value="">—</option>{sl.map((s) => <option key={s.snapshot_id} value={s.snapshot_id}>{s.snapshot_id} ({fmtTime(s.taken_at)})</option>)}</select></label>
              <label>To <select className="input" value={to} onChange={(e) => setTo(e.target.value)}><option value="">—</option>{sl.map((s) => <option key={s.snapshot_id} value={s.snapshot_id}>{s.snapshot_id} ({fmtTime(s.taken_at)})</option>)}</select></label>
              <button className="btn primary" onClick={compare}>Compare</button>
            </div>
            {diffErr && <ErrorBox message={diffErr} />}
            {diff && (
              diff.lines.every((l) => l.kind === "same") ? <Empty>No differences.</Empty> : (
                <pre className="code diff">{diff.lines.filter((l) => l.kind !== "same").map((l, i) => (
                  <div key={i} className={`dl-${l.kind}`}>{l.kind === "add" ? "+ " : "- "}{l.text}</div>))}</pre>
              )
            )}
          </>
        )}
      </Card>

      <Card title="Scan history">
        {scans.loading ? <Loading /> : (scans.data ?? []).length === 0 ? <Empty>No scans yet.</Empty> : (
          <table><thead><tr><th>Scan</th><th>Started</th><th>Status</th><th>Findings</th></tr></thead>
            <tbody>{(scans.data ?? []).map((s) => <tr key={s.scan_id}><td>{s.scan_id}</td><td>{fmtTime(s.started_at)}</td><td>{s.status}{s.error && ` — ${s.error}`}</td><td>{s.findings_count}</td></tr>)}</tbody></table>
        )}
      </Card>
    </>
  );
}
