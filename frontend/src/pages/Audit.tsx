import { api } from "../api/client";
import { Card, Empty, ErrorBox, Loading, Pill } from "../components/ui";
import { fmtTime, useAsync } from "../hooks";

export default function Audit() {
  const { data, error, loading, reload } = useAsync(() => api.listAuditLogs(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <>
      <h1>Audit log</h1>
      <Card>
        {(data ?? []).length === 0 ? <Empty>No audit entries.</Empty> : (
          <table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Result</th><th>Detail</th></tr></thead>
            <tbody>{(data ?? []).map((l) => (
              <tr key={l.log_id}><td>{fmtTime(l.at)}</td><td>{l.actor}</td><td><code>{l.action}</code></td><td>{l.target}</td>
                <td><Pill tone={l.result === "success" ? "ok" : l.result === "denied" ? "warn" : "bad"}>{l.result}</Pill></td><td>{l.detail}</td></tr>))}</tbody></table>
        )}
      </Card>
    </>
  );
}
