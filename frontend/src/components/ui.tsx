import type { ReactNode } from "react";
import type { Severity } from "../types";

export const SeverityBadge = ({ severity }: { severity: Severity }) => (
  <span className={`badge sev-${severity}`}>{severity}</span>
);

export const Pill = ({ tone, children }: { tone: "ok" | "bad" | "warn" | "muted"; children: ReactNode }) => (
  <span className={`pill pill-${tone}`}>{children}</span>
);

export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <div className="state" role="status">{label}</div>
);

export const ErrorBox = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div className="state error" role="alert">
    <strong>Something went wrong.</strong> {message}
    {onRetry && <button className="btn small" onClick={onRetry}>Retry</button>}
  </div>
);

export const Empty = ({ children }: { children: ReactNode }) => <div className="state">{children}</div>;

export const Card = ({ title, children, actions }: { title?: string; children: ReactNode; actions?: ReactNode }) => (
  <section className="card">
    {(title || actions) && (
      <header className="card-head"><h3>{title}</h3><div>{actions}</div></header>
    )}
    {children}
  </section>
);

export const CodeBlock = ({ lines }: { lines: string[] }) => (
  <pre className="code">{lines.join("\n")}</pre>
);
