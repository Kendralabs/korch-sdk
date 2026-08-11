import { useRef, useState } from "react";

// The primary dashboard view: a fan-out/fan-in multi-agent investigation console driven by
// dashboard/backend/fincrime_router.py's SSE event vocabulary (run_started/stage/superstep/
// agent_status/stream/finding/cost/assessment/human_request/resolved/run_completed). Reuses the
// design tokens and component classes already defined in index.css (--blue/--red/--amber/--teal/
// --violet/--green, .panel-*, .btn-*, .progress-bar, .log-terminal) rather than forking a new
// palette — only the layout is new (stage rail, agent grid, findings feed, assessment, HITL gate).

const STAGES = ["collect", "understand", "assess", "report"] as const;
type Stage = (typeof STAGES)[number];

const AGENT_ORDER = [
  "kyc_kyb",
  "osint_screening",
  "case_history",
  "fincrime_guardian",
  "rm_liaison",
  "reconciler",
] as const;

const AGENT_META: Record<string, { label: string; role: string; icon: string; model: string }> = {
  kyc_kyb: { label: "KYC/KYB", role: "Collect", icon: "🪪", model: "gpt-4o" },
  osint_screening: { label: "OSINT & Screening", role: "Understand", icon: "🔎", model: "gpt-4o" },
  case_history: { label: "Case History", role: "Understand", icon: "🗂", model: "gpt-4o-mini" },
  fincrime_guardian: { label: "Transaction Analysis", role: "Assess", icon: "📈", model: "gpt-4o" },
  rm_liaison: { label: "RM Liaison", role: "Assess", icon: "✉", model: "gpt-4o-mini" },
  reconciler: { label: "Reconciliation & Report", role: "Report", icon: "🧾", model: "gpt-4o" },
};

type AgentStatus = "idle" | "active" | "done";
interface AgentTrace {
  status: AgentStatus;
  model: string;
  lines: string[];
}
interface Finding {
  id: string;
  agent: string;
  severity: "critical" | "high" | "medium" | "info";
  title: string;
  summary: string;
  confidence: number;
  tool: string;
}
interface Assessment {
  grade: string;
  why: string;
  recommendation: string;
}

const DEFAULT_OBJECTIVE =
  "Investigate the unusual cross-border trade-finance activity alert on Meridian Trade " +
  "Holdings Ltd (ALRT-2026-0708) end-to-end and produce a risk-graded assessment.";

function initialAgents(): Record<string, AgentTrace> {
  const out: Record<string, AgentTrace> = {};
  for (const id of AGENT_ORDER) {
    out[id] = { status: "idle", model: AGENT_META[id].model, lines: [] };
  }
  return out;
}

export default function InvestigationConsole({ apiBase }: { apiBase: string }) {
  const [objective, setObjective] = useState(DEFAULT_OBJECTIVE);
  const [agents, setAgents] = useState<Record<string, AgentTrace>>(initialAgents());
  const [stage, setStage] = useState<Stage | null>(null);
  const [superstep, setSuperstep] = useState(0);
  const [running, setRunning] = useState(false);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [hitl, setHitl] = useState<{ open: boolean; approver?: string; resolvedOutcome?: string }>({
    open: false,
  });
  const [cost, setCost] = useState({ tokens: 0, gbp: 0 });
  const [runId, setRunId] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  function resetAll() {
    setAgents(initialAgents());
    setStage(null);
    setSuperstep(0);
    setFindings([]);
    setAssessment(null);
    setHitl({ open: false });
    setCost({ tokens: 0, gbp: 0 });
    setRunId(null);
    esRef.current?.close();
  }

  async function startRun() {
    resetAll();
    setRunning(true);

    const models = Object.fromEntries(AGENT_ORDER.map((id) => [id, agents[id].model]));
    let newRunId: string;
    try {
      const res = await fetch(`${apiBase}/api/swarm/fincrime/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective, agent_models: models }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      ({ run_id: newRunId } = await res.json());
    } catch {
      setRunning(false);
      return;
    }
    setRunId(newRunId);

    const es = new EventSource(`${apiBase}/api/swarm/fincrime/stream/${newRunId}`);
    esRef.current = es;

    es.onmessage = (ev) => {
      let event: { name: string; payload: Record<string, unknown> };
      try {
        event = JSON.parse(ev.data);
      } catch {
        return;
      }
      const { name, payload } = event;

      if (name === "stage") setStage(payload.stage as Stage);

      if (name === "superstep") setSuperstep((payload.superstep as number) ?? 0);

      if (name === "agent_status") {
        const agentId = payload.agent as string;
        setAgents((prev) =>
          prev[agentId] ? { ...prev, [agentId]: { ...prev[agentId], status: "active" } } : prev
        );
      }

      if (name === "stream") {
        const agentId = payload.agent as string;
        const text = String(payload.text ?? "");
        setAgents((prev) =>
          prev[agentId]
            ? { ...prev, [agentId]: { ...prev[agentId], lines: [...prev[agentId].lines, text].slice(-30) } }
            : prev
        );
      }

      if (name === "cost") {
        setCost((prev) => ({
          tokens: prev.tokens + (Number(payload.delta_tok) || 0),
          gbp: prev.gbp + (Number(payload.delta_gbp) || 0),
        }));
      }

      if (name === "finding") {
        const finding = payload as unknown as Finding;
        setFindings((prev) => (prev.some((f) => f.id === finding.id) ? prev : [...prev, finding]));
        setAgents((prev) =>
          prev[finding.agent] ? { ...prev, [finding.agent]: { ...prev[finding.agent], status: "done" } } : prev
        );
      }

      if (name === "human_request") {
        setHitl({ open: true, approver: String(payload.approver ?? "Reviewer") });
      }

      if (name === "resolved") {
        setHitl((prev) => ({ ...prev, open: false, resolvedOutcome: String(payload.outcome ?? "") }));
      }

      if (name === "assessment") {
        setAssessment({
          grade: String(payload.grade ?? ""),
          why: String(payload.why ?? ""),
          recommendation: String(payload.recommendation ?? ""),
        });
        setAgents((prev) =>
          prev.reconciler ? { ...prev, reconciler: { ...prev.reconciler, status: "done" } } : prev
        );
      }

      if (name === "run_completed") {
        setRunning(false);
        es.close();
      }
    };

    es.onerror = () => {
      setRunning(false);
      es.close();
    };
  }

  async function signOff(decision: "approve" | "reject") {
    if (!runId) return;
    await fetch(`${apiBase}/api/swarm/fincrime/${runId}/${decision}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approver: "Compliance Reviewer", feedback: "" }),
    });
  }

  const stageIndex = stage ? STAGES.indexOf(stage) : -1;

  return (
    <div className="ic-root">
      <div className="ic-rail">
        {STAGES.map((s, i) => (
          <div key={s} className={`ic-stage ${i === stageIndex ? "active" : i < stageIndex ? "done" : ""}`}>
            <div className="ic-stage-k">Stage {i + 1}</div>
            <div className="ic-stage-v">{s[0].toUpperCase() + s.slice(1)}</div>
          </div>
        ))}
      </div>

      <div className="ic-grid">
        <div className="ic-col">
          <div className="panel-section" style={{ borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
            <div className="panel-label">Objective</div>
            <div className="form-group">
              <textarea className="form-textarea" rows={3} value={objective} onChange={(e) => setObjective(e.target.value)} />
            </div>
            <button className="btn btn-primary btn-block" onClick={startRun} disabled={running}>
              {running ? `Investigating… (superstep ${superstep})` : "▶ Run Investigation"}
            </button>
          </div>

          <div className="ic-agents">
            {AGENT_ORDER.map((id) => {
              const meta = AGENT_META[id];
              const a = agents[id];
              return (
                <div className={`ic-agent-card ic-status-${a.status}`} key={id}>
                  <div className="ic-agent-top">
                    <span className="ic-agent-icon">{meta.icon}</span>
                    <div>
                      <div className="ic-agent-name">{meta.label}</div>
                      <div className="ic-agent-role">{meta.role}</div>
                    </div>
                    <span className={`ic-status-dot`} />
                  </div>
                  <input
                    className="form-input ic-model-input"
                    value={a.model}
                    disabled={running}
                    onChange={(e) =>
                      setAgents((prev) => ({ ...prev, [id]: { ...prev[id], model: e.target.value } }))
                    }
                  />
                  <div className="ic-agent-trace">
                    {a.lines.length === 0 ? (
                      <span className="text-muted">—</span>
                    ) : (
                      a.lines.map((line, i) => (
                        <div className="ic-trace-line" key={i}>
                          {line}
                        </div>
                      ))
                    )}
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: a.status === "done" ? "100%" : a.status === "active" ? "55%" : "0%" }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="ic-col">
          <div className="ic-findings-card">
            <div className="panel-label">Findings</div>
            {findings.length === 0 ? (
              <span className="text-muted text-xs">Findings will appear here as agents complete their work…</span>
            ) : (
              findings.map((f) => (
                <div className={`ic-finding ic-sev-${f.severity}`} key={f.id}>
                  <div className="ic-finding-head">
                    <span className={`ic-sev-badge ic-sev-${f.severity}`}>{f.severity}</span>
                    <span className="ic-finding-who">{AGENT_META[f.agent]?.label ?? f.agent}</span>
                  </div>
                  <div className="ic-finding-title">{f.title}</div>
                  <div className="ic-finding-summary">{f.summary}</div>
                  <div className="ic-conf-row">
                    <div className="ic-conf-bar">
                      <div className="ic-conf-fill" style={{ width: `${Math.round(f.confidence * 100)}%` }} />
                    </div>
                    <span>{Math.round(f.confidence * 100)}% confidence</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {assessment && (
            <div className="ic-assessment-card">
              <div className="panel-label">Reconciled Assessment</div>
              <div className="ic-grade">{assessment.grade}</div>
              <div className="ic-assessment-why">{assessment.why}</div>
              <div className="ic-rec">
                <div className="ic-rec-k">Recommendation</div>
                <div className="ic-rec-v">{assessment.recommendation}</div>
              </div>
            </div>
          )}

          {hitl.open && (
            <div className="ic-hitl-gate">
              <div className="ic-hitl-head">🛡 Sign-off required</div>
              <div className="text-sm text-muted">Awaiting: {hitl.approver}</div>
              <div className="ic-hitl-actions">
                <button className="btn btn-danger btn-sm" onClick={() => signOff("reject")}>
                  ✗ Reject
                </button>
                <button className="btn btn-success btn-sm" onClick={() => signOff("approve")}>
                  ✓ Approve &amp; Continue
                </button>
              </div>
            </div>
          )}
          {!hitl.open && hitl.resolvedOutcome && (
            <div className="text-xs text-muted" style={{ padding: "0 4px" }}>
              {hitl.resolvedOutcome}
            </div>
          )}
        </div>
      </div>

      <div className="ic-dock">
        <button className="btn btn-ghost btn-sm" onClick={resetAll} disabled={running}>
          ■ Reset
        </button>
        <div className="ic-spacer" />
        <div className="ic-cost-meter">
          <span className="text-muted text-xs">Est. cost</span>
          <span className="font-mono text-xs">£{cost.gbp.toFixed(4)}</span>
          <span className="text-muted text-xs">·</span>
          <span className="font-mono text-xs">{cost.tokens.toLocaleString()} tok (est.)</span>
        </div>
      </div>
    </div>
  );
}
