import { useState } from "react";
import { api } from "../api/client";
import type { ExplainResponse, Finding } from "../types";
import { Card, ErrorBox, Loading, Pill } from "./ui";

export default function AiExplain({ finding }: { finding: Finding }) {
  const [res, setRes] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");

  const ask = async () => {
    setLoading(true); setError(null);
    try { setRes(await api.explainFinding({ finding, question: question.trim() || undefined })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  const ex = res?.explanation;
  return (
    <Card title="AI explanation">
      <p className="muted small">
        AI explains evidence only. It cannot connect to devices or run commands; any change must go through Preview → Approve → Execute.
      </p>
      <div className="row">
        <input className="input grow" placeholder="Optional follow-up question…" value={question} maxLength={500}
          onChange={(e) => setQuestion(e.target.value)} />
        <button className="btn primary" onClick={ask} disabled={loading}>{loading ? "Thinking…" : "Explain"}</button>
      </div>
      {loading && <Loading label="Asking assistant…" />}
      {error && <ErrorBox message={error} />}
      {res?.rejected_reason && (
        <div className="state error" role="alert">Response rejected: {res.rejected_reason}</div>
      )}
      {ex && (
        <div className="ai-answer">
          <p><strong>{ex.summary}</strong></p>
          <p>{ex.why_it_matters}</p>
          <p className="small">Confidence: <Pill tone={ex.confidence === "high" ? "ok" : ex.confidence === "low" ? "bad" : "warn"}>{ex.confidence}</Pill> · Provider: {res?.provider}</p>
          {ex.caveats.length > 0 && <ul className="small">{ex.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>}
          {ex.suggested_action && (
            <p className="small">Suggested action: <code>{ex.suggested_action}</code> {JSON.stringify(ex.suggested_params)} — create it from the Remediation page to preview and approve.</p>
          )}
        </div>
      )}
    </Card>
  );
}
