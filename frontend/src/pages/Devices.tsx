import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card, Empty, ErrorBox, Loading, Pill } from "../components/ui";
import { fmtTime, useAsync } from "../hooks";

export default function Devices() {
  const { data, error, loading, reload } = useAsync(() => api.listDevices(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const act = async (id: string, kind: "test" | "scan") => {
    setBusy(`${kind}:${id}`); setMsg(null);
    try {
      if (kind === "test") await api.testConnection(id); else await api.runScan(id);
      setMsg({ ok: true, text: kind === "test" ? "Connection test finished." : "Scan completed." });
      reload();
    } catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) }); }
    finally { setBusy(null); }
  };

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <>
      <h1>Devices</h1>
      {msg && <div className={`state ${msg.ok ? "" : "error"}`} role="status">{msg.text}</div>}
      <Card>
        {(data ?? []).length === 0 ? <Empty>No devices in inventory.</Empty> : (
          <table>
            <thead><tr><th>Hostname</th><th>IP</th><th>Role</th><th>Model / IOS</th><th>Connection</th><th>Last scan</th><th /></tr></thead>
            <tbody>{(data ?? []).map((d) => (
              <tr key={d.device_id}>
                <td><Link to={`/devices/${d.device_id}`}>{d.hostname}</Link></td>
                <td>{d.ip_address}</td><td>{d.role}</td><td>{d.model}<br /><span className="muted small">{d.ios_version}</span></td>
                <td><Pill tone={d.connection_status === "reachable" ? "ok" : d.connection_status === "unreachable" ? "bad" : "muted"}>{d.connection_status}</Pill>
                  {d.last_error && <div className="small err-text">{d.last_error}</div>}</td>
                <td>{fmtTime(d.last_scan_at)}</td>
                <td className="nowrap">
                  <button className="btn small" disabled={!!busy} onClick={() => act(d.device_id, "test")}>{busy === `test:${d.device_id}` ? "Testing…" : "Test connection"}</button>{" "}
                  <button className="btn small primary" disabled={!!busy} onClick={() => act(d.device_id, "scan")}>{busy === `scan:${d.device_id}` ? "Scanning…" : "Run scan"}</button>
                </td>
              </tr>))}</tbody>
          </table>
        )}
      </Card>
    </>
  );
}
