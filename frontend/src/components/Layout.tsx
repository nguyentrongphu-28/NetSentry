import { NavLink, Outlet } from "react-router-dom";
import { USE_MOCK } from "../api/client";

const links = [
  ["/", "Dashboard"], ["/devices", "Devices"], ["/findings", "Findings"],
  ["/remediation", "Remediation"], ["/audit", "Audit log"],
] as const;

export default function Layout() {
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">NetSentry</div>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>{label}</NavLink>
          ))}
        </nav>
        {USE_MOCK && <div className="mockflag">Mock data mode</div>}
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  );
}
