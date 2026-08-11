import { useEffect, useState } from "react";
import InvestigationConsole from "./InvestigationConsole";
import SupportEscalationDemo from "./SupportEscalationDemo";
import ResearcherDemo from "./ResearcherDemo";

// Empty string in production (behind the nginx reverse proxy, same-origin /api/*); defaults to the
// local dev backend otherwise. Configure via VITE_API_BASE at build time (see .env.example).
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

type Swarm = "fincrime" | "support-escalation" | "researcher";

const SWARMS: { id: Swarm; label: string; icon: string }[] = [
  { id: "fincrime", label: "Financial Crime Investigation", icon: "🕵" },
  { id: "support-escalation", label: "Support Escalation", icon: "🎫" },
  { id: "researcher", label: "General Researcher", icon: "🔬" },
];

interface TracingStatus {
  langsmith_tracing: boolean;
  kcg_tracing: boolean;
}

function TracingBadge({ label, active }: { label: string; active: boolean }) {
  return (
    <span className={`tracing-badge ${active ? "tracing-badge-on" : "tracing-badge-off"}`}>
      <span className="tracing-badge-dot" />
      {label}
    </span>
  );
}

export default function App() {
  const [swarm, setSwarm] = useState<Swarm>("fincrime");
  const [tracing, setTracing] = useState<TracingStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/config`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setTracing(data);
      })
      .catch(() => {
        if (!cancelled) setTracing(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-logo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5" />
            <line x1="12" y1="2" x2="12" y2="22" />
            <line x1="2" y1="8.5" x2="22" y2="8.5" />
            <line x1="2" y1="15.5" x2="22" y2="15.5" />
          </svg>
          Korchestrator SDK
        </div>
        <span className="topbar-version">v0.1.0</span>
        {tracing && (
          <div className="tracing-badges">
            <TracingBadge label="LangSmith" active={tracing.langsmith_tracing} />
            <TracingBadge label="KCG" active={tracing.kcg_tracing} />
          </div>
        )}
        <div className="topbar-spacer" />
        <div className="ic-swarm-select">
          {SWARMS.map((s) => (
            <button
              key={s.id}
              className={`btn btn-sm ${swarm === s.id ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setSwarm(s.id)}
            >
              {s.icon} {s.label}
            </button>
          ))}
        </div>
      </header>

      {swarm === "fincrime" && <InvestigationConsole apiBase={API_BASE} />}
      {swarm === "support-escalation" && <SupportEscalationDemo apiBase={API_BASE} />}
      {swarm === "researcher" && <ResearcherDemo apiBase={API_BASE} />}
    </div>
  );
}
